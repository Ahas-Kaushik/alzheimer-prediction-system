"""Manages the full cognitive test session lifecycle.

The session is driven from the frontend (React GazeTracker component).
Gaze metrics are computed browser-side via MediaPipe FaceMesh (not the Python
EyeTracker, which cannot access the browser webcam) and submitted with each
response. The backend keeps session state in memory keyed by session_id.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.cognitive_test.object_display import (
    Stimulus,
    StimulusResult,
    build_stimulus_sequence,
    create_result,
    record_response,
)
from backend.cognitive_test.reaction_analyzer import compute_scores
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_sessions: dict[str, "TestSession"] = {}


@dataclass
class TestSession:
    session_id: str
    patient_id: str
    stimuli: list[Stimulus]
    results: list[StimulusResult]
    current_index: int = 0
    started_at: float = field(default_factory=time.time)
    finished: bool = False
    # Accumulated browser gaze metrics (updated on each submit_response call)
    accumulated_gaze_stability: list[float] = field(default_factory=list)
    accumulated_saccades: int = 0
    final_scores: Optional[dict] = None


def start_session(patient_id: str) -> dict:
    """Initialize and store a new test session, returning session metadata."""
    session_id = f"COG-{uuid.uuid4().hex[:8].upper()}"
    stimuli = build_stimulus_sequence(
        n_target_objects=4,
        n_target_words=3,
        n_foils=3,
        duration_ms=settings.cognitive_test_stimulus_duration_ms,
    )
    session = TestSession(
        session_id=session_id,
        patient_id=patient_id,
        stimuli=stimuli,
        results=[],
    )
    _sessions[session_id] = session
    logger.info(f"Cognitive test session started: {session_id} for patient {patient_id}")

    first = stimuli[0] if stimuli else None
    return {
        "session_id": session_id,
        "total_stimuli": sum(1 for s in stimuli if not s.is_warmup),
        "warmup_count": sum(1 for s in stimuli if s.is_warmup),
        "current_stimulus": _stimulus_to_dict(first),
    }


def get_current_stimulus(session_id: str) -> Optional[dict]:
    session = _sessions.get(session_id)
    if session is None or session.finished:
        return None
    if session.current_index >= len(session.stimuli):
        return None
    return _stimulus_to_dict(session.stimuli[session.current_index])


def submit_response(
    session_id: str,
    correct: bool,
    browser_gaze_stability: float = 1.0,
    browser_saccade_count: int = 0,
) -> dict:
    """Record a patient's response to the current stimulus and advance to next.

    browser_gaze_stability: from MediaPipe FaceMesh in browser (0.0–1.0).
    browser_saccade_count: cumulative saccades from browser tracker.
    """
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    if session.finished:
        raise ValueError("Session already finished")

    # Accumulate browser gaze metrics
    session.accumulated_gaze_stability.append(browser_gaze_stability)
    session.accumulated_saccades = max(session.accumulated_saccades, browser_saccade_count)

    stim = session.stimuli[session.current_index]
    shown_at = session.started_at + session.current_index * (
        settings.cognitive_test_stimulus_duration_ms / 1000.0
        + settings.cognitive_test_isi_ms / 1000.0
    )
    result = create_result(stim, shown_at)
    result = record_response(result, correct)
    session.results.append(result)
    session.current_index += 1

    if session.current_index >= len(session.stimuli):
        return _finalize_session(session)

    next_stim = session.stimuli[session.current_index]
    return {"status": "ongoing", "next_stimulus": _stimulus_to_dict(next_stim)}


def _finalize_session(session: TestSession) -> dict:
    session.finished = True

    # Use averaged browser gaze stability (more accurate than Python EyeTracker)
    if session.accumulated_gaze_stability:
        gaze_stability = sum(session.accumulated_gaze_stability) / len(session.accumulated_gaze_stability)
    else:
        gaze_stability = 0.5  # neutral default if no browser data

    saccade_count = session.accumulated_saccades

    scores = compute_scores(session.results, saccade_count, gaze_stability)
    session.final_scores = scores
    logger.info(
        f"Session {session.session_id} finished: "
        f"cognitive_index={scores['cognitive_index']}, derived_mmse={scores['derived_mmse']}"
    )
    return {"status": "completed", "scores": scores}


def get_session_scores(session_id: str) -> Optional[dict]:
    session = _sessions.get(session_id)
    if session is None:
        return None
    if session.final_scores is not None:
        return session.final_scores
    if not session.finished:
        return None
    # Recompute if needed
    gaze_stability = (
        sum(session.accumulated_gaze_stability) / len(session.accumulated_gaze_stability)
        if session.accumulated_gaze_stability else 0.5
    )
    return compute_scores(session.results, session.accumulated_saccades, gaze_stability)


def get_session_patient_id(session_id: str) -> Optional[str]:
    """Return the patient_id for a session (so routes can persist scores)."""
    session = _sessions.get(session_id)
    return session.patient_id if session else None


def _stimulus_to_dict(s: Optional[Stimulus]) -> Optional[dict]:
    if s is None:
        return None
    return {
        "index": s.index,
        "kind": s.kind,
        "label": s.label,
        "image_path": s.image_path,
        "duration_ms": s.duration_ms,
        "is_warmup": s.is_warmup,
        "is_target": s.is_target,
    }
