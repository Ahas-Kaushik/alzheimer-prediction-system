from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents import agent3_cognitive_test
from backend.knowledge_graph import patient_store
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class StartTestIn(BaseModel):
    patient_id: str


class SubmitResponseIn(BaseModel):
    correct: bool
    # Browser-computed gaze metrics from GazeTracker.jsx (MediaPipe FaceMesh)
    gaze_stability: float = 1.0
    saccade_count: int = 0


@router.post("/start")
async def start_test(body: StartTestIn) -> dict:
    """Initialize a new cognitive test session for a patient."""
    try:
        return agent3_cognitive_test.start(body.patient_id)
    except Exception as e:
        logger.error(f"start_test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/result")
async def submit_result(session_id: str, body: SubmitResponseIn) -> dict:
    """Submit the patient's response for the current stimulus.

    When the test completes, scores are immediately persisted to the patient store
    so that (1) the pre-flight checklist on the Prediction tab reflects completion,
    and (2) the prediction pipeline can automatically use the cognitive scores
    without requiring a separate session ID handoff.
    """
    try:
        result = agent3_cognitive_test.submit_response(
            session_id,
            body.correct,
            browser_gaze_stability=body.gaze_stability,
            browser_saccade_count=body.saccade_count,
        )

        if result.get("status") == "completed":
            scores = result["scores"]
            logger.info(
                f"Session {session_id} completed: "
                f"cognitive_index={scores.get('cognitive_index')}, "
                f"discriminability={scores.get('discriminability')}, "
                f"derived_mmse={scores.get('derived_mmse')}"
            )
            # Persist to patient store so the pre-flight check and orchestrator can use it.
            patient_id = agent3_cognitive_test.get_session_patient_id(session_id)
            if patient_id:
                try:
                    visit = patient_store.create_visit(patient_id, notes="cognitive_test")
                    patient_store.save_cognitive_test(patient_id, visit["visit_id"], scores)
                    logger.info(
                        f"Cognitive test saved for patient {patient_id} "
                        f"(visit {visit['visit_id']})"
                    )
                except Exception as save_err:
                    # Non-fatal: scores are still returned to the frontend
                    logger.warning(f"Could not persist cognitive test scores: {save_err}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"submit_result failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/scores")
async def get_scores(session_id: str) -> dict:
    """Get final scores for a completed session."""
    scores = agent3_cognitive_test.get_scores(session_id)
    return scores


@router.get("/history/{patient_id}")
async def get_cognitive_history(patient_id: str) -> list:
    """Get all cognitive test records for a patient."""
    try:
        return patient_store.get_cognitive_tests(patient_id)
    except Exception as e:
        logger.error(f"get_cognitive_history failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
