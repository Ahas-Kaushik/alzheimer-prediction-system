"""Builds the complete digital twin data payload from prediction outputs.

Payload spec matches Section 9.7 of PROJECT_KNOWLEDGE.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from backend.digital_twin.region_mapper import compute_neuron_connectivity, map_regions
from backend.digital_twin.timeline_tracker import build_longitudinal, compute_delta
from backend.knowledge_graph import patient_store
from backend.utils.logger import get_logger

logger = get_logger(__name__)

AlzheimerStage = Literal["Normal", "MCI", "AD"]


def generate(
    patient_id: str,
    current_stage: AlzheimerStage,
    current_confidence: float,
    cognitive_index: Optional[float] = None,
) -> dict:
    """Build the full digital twin payload for a patient.

    Args:
        patient_id: Patient identifier.
        current_stage: Latest predicted Alzheimer's stage.
        current_confidence: Classifier confidence for the current stage.
        cognitive_index: Cognitive test index from the current visit.

    Returns:
        Dict matching the DigitalTwinOut schema.
    """
    regions = map_regions(current_stage, current_confidence)
    connectivity = compute_neuron_connectivity(current_stage, current_confidence)

    # Load prediction history for longitudinal data and delta
    prediction_rows = patient_store.get_predictions(patient_id)
    longitudinal = build_longitudinal(prediction_rows)

    previous_stage: Optional[str] = None
    if len(prediction_rows) >= 2:
        previous_stage = prediction_rows[-2].get("stage")
    delta = compute_delta(previous_stage, current_stage)

    # Inject cognitive_index into the latest longitudinal point
    if longitudinal and cognitive_index is not None:
        longitudinal[-1]["cognitive_index"] = cognitive_index

    payload = {
        "patient_id": patient_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_stage": current_stage,
        "current_confidence": current_confidence,
        "regions": regions,
        "longitudinal": longitudinal,
        "neuron_connectivity": connectivity,
        "delta_from_last": delta,
    }

    # Persist to store
    try:
        visits = patient_store.get_visits(patient_id)
        visit_id = visits[-1]["visit_id"] if visits else "unknown"
        patient_store.save_digital_twin(patient_id, visit_id, payload)
    except Exception as e:
        logger.warning(f"Could not persist digital twin: {e}")

    return payload
