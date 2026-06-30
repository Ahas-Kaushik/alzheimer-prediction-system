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
                confidence=float(r["confidence"]) if r.get("confidence") else 0.0,
                contributing_factors=_parse_list(r.get("contributing_factors", "[]")),
                run_date=datetime.fromisoformat(r["run_date"]) if r.get("run_date") else datetime.now(timezone.utc),
                mri_path=r.get("mri_path") or None,
                pet_path=r.get("pet_path") or None,
                gradcam_path=r.get("gradcam_path") or None,
                cognitive_index=float(r["cognitive_index"]) if r.get("cognitive_index") else None,
                ssim_score=float(r["ssim_score"]) if r.get("ssim_score") else None,
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
            confidence=float(row["confidence"]) if row.get("confidence") else 0.0,
            contributing_factors=_parse_list(row.get("contributing_factors", "[]")),
            run_date=datetime.fromisoformat(row["run_date"]) if row.get("run_date") else datetime.now(timezone.utc),
            mri_path=row.get("mri_path") or None,
            pet_path=row.get("pet_path") or None,
            gradcam_path=row.get("gradcam_path") or None,
            cognitive_index=float(row["cognitive_index"]) if row.get("cognitive_index") else None,
            ssim_score=float(row["ssim_score"]) if row.get("ssim_score") else None,
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
