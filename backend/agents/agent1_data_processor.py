"""Agent 1 — Multimodal Data Processing Agent.

Fuses MRI features, synthetic PET features, clinical features, and cognitive
scores into a single vector, then runs the Alzheimer's classifier to produce
a stage prediction with confidence.

Input/output spec matches Section 6 (Agent 1) of PROJECT_KNOWLEDGE.md.
"""
from __future__ import annotations

from typing import Optional

import torch

from backend.models.classifier.alzheimer_classifier import predict
from backend.models.classifier.clinical_rules import apply_override
from backend.models.classifier.feature_extractor import extract_image_features
from backend.utils.data_normalizer import normalize_clinical_features, normalize_cognitive_scores
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Top-feature labels (positional, matched to the fused vector layout)
_FEATURE_LABELS = (
    ["MRI_feat"] * 512 +
    ["PET_feat"] * 512 +
    ["clinical_age", "clinical_education", "clinical_mmse", "clinical_moca",
     "clinical_cdr", "clinical_amyloid", "clinical_tau", "clinical_ptau",
     "clinical_hemoglobin", "clinical_glucose", "clinical_cholesterol",
     "clinical_hdl", "clinical_ldl", "clinical_triglycerides",
     "clinical_vitB12", "clinical_tsh", "clinical_hippocampal",
     "clinical_cortical", "clinical_wmh",
     "clinical_smoking", "clinical_diabetes", "clinical_hypertension",
     "clinical_depression", "clinical_familyAD",
     "clinical_gender", "clinical_apoe4"] +
    ["cog_reaction_speed", "cog_rt_std", "cog_accuracy", "cog_gaze",
     "cog_saccade", "cog_correct_ratio", "cog_index", "cog_index2"]
)


def run(
    mri_tensor: torch.Tensor,
    pet_tensor: torch.Tensor,
    clinical_features: dict,
    cognitive_scores: dict,
) -> dict:
    """Execute the full multimodal fusion and classification pipeline.

    Args:
        mri_tensor: (1, 1, 256, 256) MRI in [-1, 1].
        pet_tensor: (1, 1, 256, 256) synthetic PET in [-1, 1].
        clinical_features: Raw clinical feature dict (see Section 14).
        cognitive_scores: Agent 3 output dict (see Section 6, Agent 3 Output).

    Returns:
        Dict with: stage, confidence, contributing_factors, feature_vector.
    """
    logger.info("Agent1: extracting image features")

    mri_feats = extract_image_features(mri_tensor).tolist()   # 512-d
    pet_feats = extract_image_features(pet_tensor).tolist()   # 512-d

    # Inject derived MMSE from cognitive test if no clinical MMSE provided
    derived_mmse = cognitive_scores.get("derived_mmse")
    if derived_mmse is not None and not clinical_features.get("mmse_score"):
        clinical_features = {**clinical_features, "mmse_score": float(derived_mmse)}
        logger.info(f"Agent1: using derived MMSE={derived_mmse} from cognitive test")

    clinical_vec = normalize_clinical_features(clinical_features)  # N-d
    cognitive_vec = normalize_cognitive_scores(cognitive_scores)   # 8-d

    fused = mri_feats + pet_feats + clinical_vec + cognitive_vec

    logger.info(f"Agent1: fused vector dim={len(fused)}, running classifier")
    result = predict(fused, backend="mlp")

    # Clinical biomarker override — escalates to AD/MCI when lab evidence is
    # unambiguous, regardless of the imaging/cognitive-driven model output.
    result = apply_override(result, clinical_features, cognitive_scores)

    contributing = _merge_factors(
        _top_contributing_factors(fused, result["probabilities"]),
        result.get("biomarker_reasons", []),
        result.get("override_applied", False),
    )

    logger.info(
        f"Agent1 result: stage={result['stage']}, confidence={result['confidence']:.3f}, "
        f"ad_points={result.get('ad_points')}, override={result.get('override_applied')}"
    )
    return {
        "stage": result["stage"],
        "confidence": result["confidence"],
        "contributing_factors": contributing,
        "feature_vector": fused,
        "probabilities": result["probabilities"],
    }


def run_with_precomputed_mri_feats(
    mri_feats: list[float],
    pet_tensor: torch.Tensor,
    clinical_features: dict,
    cognitive_scores: dict,
) -> dict:
    """Like run(), but accepts pre-averaged MRI features (multi-scan ensemble).

    Used by Agent 4 when multiple MRI scans exist — features are averaged
    before calling this function.
    """
    logger.info("Agent1: using pre-averaged MRI features (multi-scan ensemble)")

    pet_feats = extract_image_features(pet_tensor).tolist()

    derived_mmse = cognitive_scores.get("derived_mmse")
    if derived_mmse is not None and not clinical_features.get("mmse_score"):
        clinical_features = {**clinical_features, "mmse_score": float(derived_mmse)}

    clinical_vec = normalize_clinical_features(clinical_features)
    cognitive_vec = normalize_cognitive_scores(cognitive_scores)

    fused = mri_feats + pet_feats + clinical_vec + cognitive_vec

    logger.info(f"Agent1: fused dim={len(fused)}, running classifier")
    result = predict(fused, backend="mlp")
    result = apply_override(result, clinical_features, cognitive_scores)
    contributing = _merge_factors(
        _top_contributing_factors(fused, result["probabilities"]),
        result.get("biomarker_reasons", []),
        result.get("override_applied", False),
    )

    return {
        "stage": result["stage"],
        "confidence": result["confidence"],
        "contributing_factors": contributing,
        "feature_vector": fused,
        "probabilities": result["probabilities"],
    }


def _top_contributing_factors(fused: list[float], probs: dict) -> list[str]:
    """Heuristic: identify top 3 feature groups by absolute magnitude in fused vector."""
    import numpy as np

    arr = np.abs(fused)
    labels = _FEATURE_LABELS[:len(arr)]

    # Aggregate by named group prefix
    groups: dict[str, float] = {}
    for val, label in zip(arr, labels):
        prefix = label.split("_")[0]
        groups[prefix] = groups.get(prefix, 0.0) + float(val)

    # Clinical and cognitive individual features — break out top ones
    clinical_vals: dict[str, float] = {}
    cog_vals: dict[str, float] = {}
    for val, label in zip(arr, labels):
        if label.startswith("clinical_"):
            clinical_vals[label] = float(val)
        elif label.startswith("cog_"):
            cog_vals[label] = float(val)

    top_clinical = sorted(clinical_vals, key=clinical_vals.get, reverse=True)[:2]  # type: ignore
    top_cog = sorted(cog_vals, key=cog_vals.get, reverse=True)[:1]                 # type: ignore

    factors = (
        [_humanize(f) for f in top_clinical] +
        [_humanize(f) for f in top_cog]
    )
    return factors[:3]


def _merge_factors(model_factors: list[str], biomarker_reasons: list[str], override_applied: bool) -> list[str]:
    """Combine model-derived factors with biomarker reasons.

    When the biomarker override fired, its clinical reasons are the primary
    explanation and lead the list; otherwise model factors lead and a couple of
    supporting biomarker notes are appended.
    """
    if override_applied and biomarker_reasons:
        merged = list(biomarker_reasons[:3])
        for f in model_factors:
            if len(merged) >= 4:
                break
            if f not in merged:
                merged.append(f)
        return merged
    merged = list(model_factors)
    for r in biomarker_reasons[:2]:
        if r not in merged:
            merged.append(r)
    return merged[:4]


def _humanize(key: str) -> str:
    return key.replace("clinical_", "").replace("cog_", "cognitive ").replace("_", " ").title()
