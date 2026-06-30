from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas.prediction_schema import DigitalTwinOut
from backend.digital_twin import twin_generator
from backend.digital_twin.timeline_tracker import build_longitudinal
from backend.knowledge_graph import patient_store
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/{patient_id}", response_model=DigitalTwinOut)
async def get_twin(patient_id: str) -> DigitalTwinOut:
    """Get the latest digital twin payload for a patient.

    If no twin has been generated yet, auto-generates one from the latest prediction.
    """
    try:
        pred = patient_store.get_latest_prediction(patient_id)
        if pred is None:
            raise HTTPException(status_code=404, detail="No prediction found — run prediction pipeline first")

        stage = pred.get("stage", "Normal")
        confidence = float(pred.get("confidence", 0.5))
        cognitive_index = float(pred["cognitive_index"]) if pred.get("cognitive_index") else None

        payload = twin_generator.generate(patient_id, stage, confidence, cognitive_index)
        return DigitalTwinOut(**payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_twin failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}/history")
async def get_twin_history(patient_id: str) -> dict:
    """Get the longitudinal twin history (all predictions as timeline points)."""
    try:
        rows = patient_store.get_predictions(patient_id)
        longitudinal = build_longitudinal(rows)
        return {"patient_id": patient_id, "longitudinal": longitudinal}
    except Exception as e:
        logger.error(f"get_twin_history failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
