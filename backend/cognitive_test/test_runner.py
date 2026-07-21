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
from backend.cognitive_test.reaction_analyzer import MIN_VALID_RT_MS, compute_scores
from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_sessions: dict[str, "TestSession"] = {}

# Standard (tougher) test = 13 scored items; reset test = 20 scored items.
_STANDARD_COUNTS = dict(n_target_objects=6, n_target_words=3, n_foils=4)
_RESET_COUNTS = dict(n_target_objects=8, n_target_words=4, n_foils=8)


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
    accumulated_on_screen: list[bool] = field(default_factory=list)
    final_scores: Optional[dict] = None
    # Integrity tracking for spam / reset behaviour
    too_fast_count: int = 0
    reset_count: int = 0


def start_session(patient_id: str) -> dict:
    """Initialize and store a new test session, returning session metadata."""
    session_id = f"COG-{uuid.uuid4().hex[:8].upper()}"
    stimuli = build_stimulus_sequence(
        duration_ms=settings.cognitive_test_stimulus_duration_ms,
        **_STANDARD_COUNTS,
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
    reaction_time_ms: Optional[float] = None,
    gaze_on_screen: bool = True,
) -> dict:
    """Record a patient's response to the current stimulus and advance to next.

    browser_gaze_stability: from MediaPipe FaceMesh in browser (0.0–1.0).
    browser_saccade_count: cumulative saccades from browser tracker.
    reaction_time_ms: browser-measured time from stimulus onset to keypress.
    gaze_on_screen: whether the browser tracker saw the patient looking at the
        screen when they answered.

    May return {'status': 'reset', ...} when spam / mashing behaviour is detected,
    in which case the test restarts with a longer (20-item) sequence.
    """
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    if session.finished:
        raise ValueError("Session already finished")

    # Accumulate browser gaze metrics
    session.accumulated_gaze_stability.append(browser_gaze_stability)
    session.accumulated_saccades = max(session.accumulated_saccades, browser_saccade_count)
    session.accumulated_on_screen.append(bool(gaze_on_screen))

    stim = session.stimuli[session.current_index]
    shown_at = session.started_at + session.current_index * (
        settings.cognitive_test_stimulus_duration_ms / 1000.0
        + settings.cognitive_test_isi_ms / 1000.0
    )
    result = create_result(stim, shown_at)
    result = record_response(result, correct, reaction_time_ms=reaction_time_ms)
    result.gaze_on_screen = bool(gaze_on_screen)
    session.results.append(result)
    session.current_index += 1

    # Track impulsive (too-fast) presses for spam detection
    if result.reaction_time_ms is not None and result.reaction_time_ms < MIN_VALID_RT_MS:
        session.too_fast_count += 1

    # ── Spam / mashing detection → reset once with a longer test ──────────────
    if session.reset_count == 0 and _looks_like_spam(session):
        return _reset_session(session)

    if session.current_index >= len(session.stimuli):
        return _finalize_session(session)

    next_stim = session.stimuli[session.current_index]
    return {"status": "ongoing", "next_stimulus": _stimulus_to_dict(next_stim)}


def _looks_like_spam(session: TestSession) -> bool:
    """Heuristic: is the patient mashing buttons rather than genuinely responding?

    We deliberately do NOT flag "alternating" or plain "all-same" response
    patterns, because a genuine responder to a shuffled target/foil sequence can
    legitimately produce those patterns. The robust signal for mashing is
    *impulsive speed*: pressing faster than a person could actually read the item.
    """
    # Several impulsive (too-fast) presses → almost certainly not reading.
    if session.too_fast_count >= 3:
        return True

    # All-same button AND consistently too fast = blind mashing of one key.
    responses = [r.user_responded for r in session.results if r.user_responded is not None]
    rts = [r.reaction_time_ms for r in session.results if r.reaction_time_ms is not None]
    if len(responses) >= 6 and len(set(responses)) <= 1 and rts:
        avg_rt = sum(rts) / len(rts)
        if avg_rt < 600:
            return True
    return False


def _reset_session(session: TestSession) -> dict:
    """Rebuild the session with a longer 20-item test and clear progress."""
    session.reset_count += 1
    session.stimuli = build_stimulus_sequence(
        duration_ms=settings.cognitive_test_stimulus_duration_ms,
        **_RESET_COUNTS,
    )
    session.results = []
    session.current_index = 0
    session.started_at = time.time()
    session.too_fast_count = 0
    session.accumulated_gaze_stability = []
    session.accumulated_on_screen = []
    logger.info(f"Session {session.session_id} RESET (spam detected) → 20-item test")

    first = session.stimuli[0] if session.stimuli else None
    return {
        "status": "reset",
        "reason": "Button mashing / not reading detected — the test was restarted "
                  "with a longer sequence. Please read each item and answer carefully.",
        "reset_count": session.reset_count,
        "total_stimuli": sum(1 for s in session.stimuli if not s.is_warmup),
        "current_stimulus": _stimulus_to_dict(first),
    }


def _finalize_session(session: TestSession) -> dict:
    session.finished = True

    # Use averaged browser gaze stability (more accurate than Python EyeTracker)
    if session.accumulated_gaze_stability:
        gaze_stability = sum(session.accumulated_gaze_stability) / len(session.accumulated_gaze_stability)
    else:
        gaze_stability = 0.5  # neutral default if no browser data

    saccade_count = session.accumulated_saccades
    on_screen_ratio = (
        sum(1 for v in session.accumulated_on_screen if v) / len(session.accumulated_on_screen)
        if session.accumulated_on_screen else None
    )

    scores = compute_scores(
        session.results, saccade_count, gaze_stability, on_screen_ratio=on_screen_ratio
    )
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
    on_screen_ratio = (
        sum(1 for v in session.accumulated_on_screen if v) / len(session.accumulated_on_screen)
        if session.accumulated_on_screen else None
    )
    return compute_scores(
        session.results, session.accumulated_saccades, gaze_stability,
        on_screen_ratio=on_screen_ratio,
    )


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
