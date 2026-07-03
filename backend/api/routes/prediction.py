from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.agents import agent4_orchestrator
from backend.api.schemas.prediction_schema import PredictionOut, PredictionRunIn
from backend.knowledge_graph import patient_store
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/run", response_model=PredictionOut)
async def run_prediction(body: PredictionRunIn) -> PredictionOut:
    """Run the full agent pipeline for a patient visit and return the prediction."""
    try:
        clinical = body.clinical_features or {}
        # Preferred path: LangGraph orchestration (validate → predict → RAG reason).
        # Falls back to the direct orchestrator if LangGraph is unavailable.
        try:
            from backend.agents.graph_pipeline import run_graph_pipeline
            result = run_graph_pipeline(
                patient_id=body.patient_id,
                scan_id=body.scan_id,
                clinical_features=clinical,
                cognitive_session_id=body.cognitive_session_id,
                skip_cognitive_test=body.skip_cognitive_test,
            )
        except ImportError:
            result = agent4_orchestrator.run_pipeline(
                patient_id=body.patient_id,
                scan_id=body.scan_id,
                clinical_features=clinical,
                cognitive_session_id=body.cognitive_session_id,
                skip_cognitive_test=body.skip_cognitive_test,
            )
        return PredictionOut(
            pred_id=result["pred_id"],
            patient_id=result["patient_id"],
            visit_id=result["visit_id"],
            stage=result["stage"],
            confidence=result["confidence"],
            contributing_factors=result["contributing_factors"],
            run_date=datetime.now(timezone.utc),
            mri_path=result.get("mri_path"),
            pet_path=result.get("pet_path"),
            gradcam_path=result.get("gradcam_path"),
            cognitive_index=result.get("cognitive_index"),
            ssim_score=result.get("ssim_score"),
            probabilities=result.get("probabilities"),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"run_prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}", response_model=list[PredictionOut])
async def get_predictions(patient_id: str) -> list[PredictionOut]:
    """Get all predictions for a patient (sorted oldest first)."""
    try:
        rows = patient_store.get_predictions(patient_id)
        return [
            PredictionOut(
                pred_id=r["pred_id"],
                patient_id=r["patient_id"],
                visit_id=r["visit_id"],
                stage=r["stage"],
                confidence=_safe_float(r.get("confidence")) or 0.0,
                contributing_factors=_parse_list(r.get("contributing_factors", "[]")),
                run_date=datetime.fromisoformat(r["run_date"]) if r.get("run_date") else datetime.now(timezone.utc),
                mri_path=r.get("mri_path") or None,
                pet_path=r.get("pet_path") or None,
                gradcam_path=r.get("gradcam_path") or None,
                cognitive_index=_safe_float(r.get("cognitive_index")),
                ssim_score=_safe_float(r.get("ssim_score")),
                probabilities=_parse_probs(r.get("probabilities"), r["stage"], _safe_float(r.get("confidence"))),
            )
            for r in rows
        ]
    except Exception as e:
        logger.error(f"get_predictions failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}/latest", response_model=PredictionOut)
async def get_latest_prediction(patient_id: str) -> PredictionOut:
    """Get the most recent prediction for a patient."""
    try:
        row = patient_store.get_latest_prediction(patient_id)
        if row is None:
            raise HTTPException(status_code=404, detail="No predictions found for patient")
        return PredictionOut(
            pred_id=row["pred_id"],
            patient_id=row["patient_id"],
            visit_id=row["visit_id"],
            stage=row["stage"],
            confidence=_safe_float(row.get("confidence")) or 0.0,
            contributing_factors=_parse_list(row.get("contributing_factors", "[]")),
            run_date=datetime.fromisoformat(row["run_date"]) if row.get("run_date") else datetime.now(timezone.utc),
            mri_path=row.get("mri_path") or None,
            pet_path=row.get("pet_path") or None,
            gradcam_path=row.get("gradcam_path") or None,
            cognitive_index=_safe_float(row.get("cognitive_index")),
            ssim_score=_safe_float(row.get("ssim_score")),
            probabilities=_parse_probs(row.get("probabilities"), row["stage"], _safe_float(row.get("confidence"))),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_latest_prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _parse_list(raw: str) -> list[str]:
    import ast
    try:
        val = ast.literal_eval(raw)
        return val if isinstance(val, list) else [str(val)]
    except Exception:
        return []


def _parse_probs(raw, stage: str, confidence: float | None) -> dict:
    """Return the Normal/MCI/AD probability distribution.

    Uses the stored JSON when present; otherwise synthesises a plausible
    distribution from the predicted stage + confidence so older predictions
    (saved before probabilities were persisted) still render sensible bars.
    """
    import json
    if raw:
        try:
            d = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(d, dict) and d:
                return {k: float(v) for k, v in d.items()}
        except Exception:
            pass
    conf = confidence if confidence is not None else 0.34
    conf = min(max(conf, 0.0), 1.0)
    other = max(0.0, (1.0 - conf) / 2.0)
    dist = {"Normal": other, "MCI": other, "AD": other}
    if stage in dist:
        dist[stage] = conf
    return dist


def _safe_float(val) -> float | None:
    """Parse a CSV cell to float, tolerating '', 'None', 'null', 'nan'."""
    if val is None:
        return None
    s = str(val).strip()
    if s.lower() in ("", "none", "null", "nan"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None
