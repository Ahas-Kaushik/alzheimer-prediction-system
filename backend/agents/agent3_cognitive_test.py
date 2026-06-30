"""Agent 3 — Patient Cognitive Test Agent.

Wraps the cognitive_test session manager. The frontend drives stimulus display
and response collection; this agent provides the session control interface
and returns the final scored output dict.
"""
from __future__ import annotations

from typing import Optional

from backend.cognitive_test import test_runner
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SCORES = {
    "reaction_time_avg_ms": 1500.0,
    "reaction_time_std_ms": 0.0,
    "identification_accuracy": 0.5,
    "gaze_stability_score": 0.5,
    "saccade_count": 20,
    "correct_count": 5,
    "total_stimuli": 10,
    "cognitive_index": 50.0,
    "derived_mmse": 15,
}


def start(patient_id: str) -> dict:
    """Initialize a new cognitive test session.

    Returns session metadata including the first stimulus to display.
    """
    return test_runner.start_session(patient_id)


def submit_response(
    session_id: str,
    correct: bool,
    browser_gaze_stability: float = 1.0,
    browser_saccade_count: int = 0,
) -> dict:
    """Record the patient's response and advance to the next stimulus.

    browser_gaze_stability and browser_saccade_count come from MediaPipe
    FaceMesh running client-side (fixes server-side webcam access limitation).

    Returns either {'status': 'ongoing', 'next_stimulus': ...}
    or {'status': 'completed', 'scores': {...}}.
    """
    return test_runner.submit_response(
        session_id,
        correct,
        browser_gaze_stability=browser_gaze_stability,
        browser_saccade_count=browser_saccade_count,
    )


def get_scores(session_id: str) -> dict:
    """Retrieve final scores for a completed session.

    Falls back to DEFAULT_SCORES if the session is unavailable
    (e.g., cognitive test was skipped).
    """
    scores = test_runner.get_session_scores(session_id)
    if scores is None:
        logger.warning(f"Session {session_id} not found — using default cognitive scores")
        return DEFAULT_SCORES
    return scores


def get_default_scores() -> dict:
    """Return neutral default scores when cognitive test is skipped."""
    return dict(DEFAULT_SCORES)


def get_session_patient_id(session_id: str) -> Optional[str]:
    """Return the patient_id associated with a session (used by the route to persist scores)."""
    return test_runner.get_session_patient_id(session_id)
