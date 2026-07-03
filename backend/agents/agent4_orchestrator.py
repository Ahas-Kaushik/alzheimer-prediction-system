"""Agent 4 — Orchestrator.

Coordinates the full prediction pipeline:
  Agent 2 (MRI → synthetic PET) → Agent 3 (cognitive test, if not cached)
  → Agent 1 (fuse → classify) → Knowledge Graph → Digital Twin

When multiple MRI scans exist, features from all scans are averaged
(ensemble of slices) before classification for improved accuracy.
"""
from __future__ import annotations

from typing import Optional

import torch

from backend.agents import agent1_data_processor, agent2_pet_synthesizer, agent3_cognitive_test
from backend.digital_twin import twin_generator
from backend.knowledge_graph import patient_store
from backend.models.classifier.feature_extractor import extract_image_features
from backend.utils.image_utils import load_mri_image
from backend.utils.logger import get_logger
from backend.config import settings

logger = get_logger(__name__)


def run_pipeline(
    patient_id: str,
    scan_id: Optional[str] = None,
    clinical_features: Optional[dict] = None,
    cognitive_session_id: Optional[str] = None,
    skip_cognitive_test: bool = False,
) -> dict:
    """Execute the complete prediction pipeline for one patient visit.

    Args:
        patient_id: Patient to run the pipeline for.
        scan_id: Specific scan ID to use; defaults to latest scan.
        clinical_features: Raw clinical feature dict.
        cognitive_session_id: ID of a completed cognitive test session to retrieve scores.
        skip_cognitive_test: If True, use default cognitive scores.

    Returns:
        Combined result dict with prediction, twin, and metadata.
    """
    logger.info(f"Orchestrator: starting pipeline for patient={patient_id}")

    # ── Step 1: Load MRI(s) ───────────────────────────────────────────────────
    # Use all scans for this patient (multi-slice ensemble)
    all_scans = patient_store.get_all_scans(patient_id)
    if not all_scans:
        raise ValueError(f"No MRI scan found for patient {patient_id}")

    # Primary scan for PET synthesis
    if scan_id:
        primary_scan = next((s for s in all_scans if s["scan_id"] == scan_id), all_scans[-1])
    else:
        primary_scan = all_scans[-1]

    primary_mri = load_mri_image(primary_scan["file_path"], size=settings.gan_image_size)

    # Load all available MRI tensors for feature averaging
    mri_tensors = []
    for scan in all_scans:
        try:
            mri_tensors.append(load_mri_image(scan["file_path"], size=settings.gan_image_size))
        except Exception as exc:
            logger.warning(f"Could not load scan {scan['scan_id']}: {exc}")
    if not mri_tensors:
        mri_tensors = [primary_mri]

    logger.info(f"Orchestrator: using {len(mri_tensors)} MRI scan(s) for ensemble features")

    # ── Step 2: Agent 2 — Synthesize PET (from primary scan) ─────────────────
    agent2_result = agent2_pet_synthesizer.run(
        mri_tensor=primary_mri,
        patient_id=patient_id,
        scan_id=primary_scan["scan_id"],
    )
    pet_tensor: torch.Tensor = agent2_result["pet_tensor"]

    pet_row = patient_store.save_synthetic_pet(
        patient_id=patient_id,
        scan_id=primary_scan["scan_id"],
        file_path=agent2_result["file_path"],
        ssim_score=agent2_result.get("ssim_score"),
        psnr_score=agent2_result.get("psnr_score"),
    )

    # ── Step 3: Agent 3 — Cognitive Scores ───────────────────────────────────
    # Priority: live session ID > latest saved test record > default neutral scores.
    if cognitive_session_id and not skip_cognitive_test:
        cognitive_scores = agent3_cognitive_test.get_scores(cognitive_session_id)
        logger.info(f"Orchestrator: loaded cognitive scores from live session {cognitive_session_id}")
    else:
        # Even when prediction is run without a live session (the common case from the
        # Prediction tab), use the most recent cognitive test that was saved to the DB
        # so that completed tests always feed into the classifier.
        saved_cog = patient_store.get_cognitive_tests(patient_id)
        if saved_cog:
            latest_cog = saved_cog[-1]
            def _flt(key: str, default: float) -> float:
                try: return float(latest_cog.get(key) or default)
                except (TypeError, ValueError): return default
            cognitive_scores = {
                "reaction_time_avg_ms":   _flt("reaction_time_avg_ms", 1500.0),
                "reaction_time_std_ms":   _flt("reaction_time_std_ms", 0.0),
                "identification_accuracy": _flt("identification_accuracy", 0.5),
                "gaze_stability_score":   _flt("gaze_stability_score", 0.5),
                "saccade_count":          int(_flt("saccade_count", 20)),
                "correct_count":          int(_flt("correct_count", 5)),
                "total_stimuli":          int(_flt("total_stimuli", 10)),
                "cognitive_index":        _flt("cognitive_index", 50.0),
                "derived_mmse":           int(_flt("derived_mmse", 15)),
            }
            logger.info(
                f"Orchestrator: loaded cognitive scores from saved record "
                f"(index={cognitive_scores['cognitive_index']}, mmse={cognitive_scores['derived_mmse']})"
            )
        else:
            cognitive_scores = agent3_cognitive_test.get_default_scores()
            logger.info("Orchestrator: using default cognitive scores (no test on record)")

    # ── Step 4: Agent 1 — Fuse + Classify (ensemble MRI features) ────────────
    # Merge explicit clinical_features with any data saved from Blood Reports form.
    # Explicit features (from ClinicalDataForm) take priority over stored report data.
    clinical = {}
    try:
        import json as _json
        saved_reports = patient_store.get_reports(patient_id)
        if saved_reports:
            raw = saved_reports[-1].get("extracted_fields_json", "") or saved_reports[-1].get("extracted_fields", "")
            if isinstance(raw, dict):
                clinical = raw
            elif raw:
                clinical = _json.loads(raw)
    except Exception as _e:
        logger.debug(f"Could not load saved report clinical data: {_e}")
    if clinical_features:
        clinical.update(clinical_features)  # explicit form data wins

    if len(mri_tensors) == 1:
        # Single scan — normal path
        agent1_result = agent1_data_processor.run(
            mri_tensor=mri_tensors[0],
            pet_tensor=pet_tensor,
            clinical_features=clinical,
            cognitive_scores=cognitive_scores,
        )
    else:
        # Multi-scan ensemble: average MRI feature vectors across all scans
        mri_feat_sum = None
        for t in mri_tensors:
            feats = extract_image_features(t)
            if mri_feat_sum is None:
                mri_feat_sum = feats
            else:
                mri_feat_sum = mri_feat_sum + feats
        avg_mri_feats = (mri_feat_sum / len(mri_tensors)).unsqueeze(0)  # (1, 512)
        # Build a pseudo-tensor from averaged features (agent1 re-extracts anyway)
        # Use primary MRI tensor but with a note that features are pre-averaged
        agent1_result = agent1_data_processor.run_with_precomputed_mri_feats(
            mri_feats=avg_mri_feats.squeeze(0).tolist(),
            pet_tensor=pet_tensor,
            clinical_features=clinical,
            cognitive_scores=cognitive_scores,
        )

    # ── Step 4.5: Grad-CAM visualization (non-critical) ──────────────────────
    gradcam_path = None
    try:
        from backend.models.classifier.gradcam import compute_gradcam, save_gradcam_overlay
        from backend.models.classifier.feature_extractor import _get_resnet
        from backend.models.classifier.alzheimer_classifier import load_mlp

        _stage_to_idx = {"Normal": 0, "MCI": 1, "AD": 2}
        _stage_idx = _stage_to_idx.get(agent1_result["stage"], 0)
        _fused_dim = len(agent1_result["feature_vector"])

        _resnet = _get_resnet()
        _mlp = load_mlp(checkpoint_path=settings.classifier_checkpoint, input_dim=_fused_dim)

        cam = compute_gradcam(mri_tensors[0], _resnet, _mlp, _stage_idx, fused_dim=_fused_dim)
        cam_path = settings.upload_path / patient_id / f"{primary_scan['scan_id']}_gradcam.png"
        save_gradcam_overlay(mri_tensors[0], cam, cam_path)
        gradcam_path = str(cam_path)
        logger.info(f"Orchestrator: Grad-CAM saved → {cam_path}")
    except Exception as _cam_exc:
        logger.warning(f"Orchestrator: Grad-CAM skipped — {_cam_exc}")

    # ── Step 5: Persist prediction ────────────────────────────────────────────
    visits = patient_store.get_visits(patient_id)
    visit_id = visits[-1]["visit_id"] if visits else patient_store.create_visit(patient_id)["visit_id"]

    _ssim = agent2_result.get("ssim_score")
    _cog_idx = cognitive_scores.get("cognitive_index")
    pred_data = {
        "stage": agent1_result["stage"],
        "confidence": str(agent1_result["confidence"]),
        "contributing_factors": str(agent1_result["contributing_factors"]),
        "mri_path": primary_scan["file_path"],
        "pet_path": agent2_result["file_path"],
        # Store empty string (not the literal "None") for missing numeric values
        # so the CSV stays parseable as float downstream.
        "cognitive_index": str(_cog_idx) if _cog_idx is not None else "",
        "ssim_score": str(_ssim) if _ssim is not None else "",
        "gradcam_path": gradcam_path or "",
    }
    pred_row = patient_store.save_prediction(patient_id, visit_id, pred_data)

    if not skip_cognitive_test and cognitive_session_id:
        patient_store.save_cognitive_test(patient_id, visit_id, cognitive_scores)

    if clinical:
        patient_store.save_clinical_features(patient_id, visit_id, clinical)

    # ── Step 6: Digital Twin ──────────────────────────────────────────────────
    twin_payload = twin_generator.generate(
        patient_id=patient_id,
        current_stage=agent1_result["stage"],
        current_confidence=agent1_result["confidence"],
        cognitive_index=cognitive_scores.get("cognitive_index"),
    )

    logger.info(
        f"Orchestrator: complete — stage={agent1_result['stage']}, "
        f"confidence={agent1_result['confidence']:.3f}, scans_used={len(mri_tensors)}"
    )

    return {
        "pred_id": pred_row["pred_id"],
        "patient_id": patient_id,
        "visit_id": visit_id,
        "stage": agent1_result["stage"],
        "confidence": agent1_result["confidence"],
        "contributing_factors": agent1_result["contributing_factors"],
        "probabilities": agent1_result.get("probabilities", {}),
        "mri_path": primary_scan["file_path"],
        "pet_path": agent2_result["file_path"],
        "ssim_score": agent2_result.get("ssim_score"),
        "cognitive_index": cognitive_scores.get("cognitive_index"),
        "digital_twin": twin_payload,
        "gradcam_path": gradcam_path,
    }
