"""Tracks longitudinal change across patient visits for the digital twin timeline."""
from __future__ import annotations

from typing import Literal, Optional

AlzheimerStage = Literal["Normal", "MCI", "AD"]
_STAGE_ORDER = {"Normal": 0, "MCI": 1, "AD": 2}


def compute_delta(previous_stage: Optional[str], current_stage: AlzheimerStage) -> str:
    """Determine whether the patient's condition improved, declined, or is stable.

    Args:
        previous_stage: Stage from the last visit, or None for the first visit.
        current_stage: Stage from the current prediction.

    Returns:
        'improved' | 'stable' | 'declined'
    """
    if previous_stage is None:
        return "stable"
    prev_idx = _STAGE_ORDER.get(previous_stage, 1)
    curr_idx = _STAGE_ORDER.get(current_stage, 1)
    if curr_idx < prev_idx:
        return "improved"
    if curr_idx > prev_idx:
        return "declined"
    return "stable"


def build_longitudinal(prediction_rows: list[dict]) -> list[dict]:
    """Convert raw prediction DB rows into the longitudinal timeline format.

    Args:
        prediction_rows: Ordered list of prediction dicts from patient_store.

    Returns:
        List of longitudinal data points for the twin payload.
    """
    _valid = {"Normal", "MCI", "AD"}
    points = []
    for row in prediction_rows:
        raw_stage = row.get("stage", "Normal")
        stage = raw_stage if raw_stage in _valid else "Normal"
        points.append({
            "visit_date": row.get("run_date", ""),
            "stage": stage,
            "cognitive_index": _safe_float(row.get("cognitive_index")),
            "hippocampal_volume_norm": None,
        })
    return points


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None
