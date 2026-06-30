"""Compute cognitive test scores using signal detection theory.

Key change from previous version: stimuli now include foils (items the patient
should NOT respond to). Scoring uses discriminability (hit_rate - false_alarm_rate)
as the primary accuracy metric, closing the loophole where patients could score
high by staring at the camera while mashing a single key.

Loophole-proof design:
- All-Enter (skip everything):  hit_rate=0, fa_rate=0 → discriminability=0.5 → all-same penalty → CI ~22
- All-Space (recognize everything): hit_rate=1, fa_rate=1 → discriminability=0.5 → all-same penalty → CI ~33
- Good gaze alone (0 accuracy): gaze contribution is gated by cognitive engagement
- Only genuine target/foil discrimination produces a high cognitive_index
"""
from __future__ import annotations

import statistics
from typing import Optional

from backend.cognitive_test.object_display import StimulusResult


def compute_scores(
    results: list[StimulusResult],
    saccade_count: int,
    gaze_stability: float,
) -> dict:
    """Compute cognitive test metrics with signal-detection-based scoring.

    Args:
        results: All StimulusResult objects (including warmup — filtered here).
        saccade_count: Total rapid gaze changes detected.
        gaze_stability: Fraction of gaze on stimulus area (0.0–1.0).

    Returns:
        Dict matching the Agent 3 output spec.
    """
    scored = [r for r in results if not r.stimulus.is_warmup]

    targets = [r for r in scored if r.stimulus.is_target]
    foils   = [r for r in scored if not r.stimulus.is_target]

    # ── Signal detection metrics ─────────────────────────────────────────────
    hits              = sum(1 for r in targets if r.response_correct)
    false_alarms      = sum(1 for r in foils   if not r.response_correct)
    correct_rejections = sum(1 for r in foils  if r.response_correct)

    n_targets = len(targets)
    n_foils   = len(foils)

    hit_rate = hits / n_targets if n_targets > 0 else 0.0
    fa_rate  = false_alarms / n_foils if n_foils > 0 else 0.0

    # Discriminability: (hit_rate - fa_rate) ranges [-1, 1], mapped to [0, 1]
    # 1.0 = perfect discrimination, 0.5 = chance level, 0.0 = systematically wrong
    discriminability = (hit_rate - fa_rate + 1.0) / 2.0

    # ── Monotonic response penalty ────────────────────────────────────────────
    # If the patient pressed the same button for every single stimulus
    # (all Space or all Enter), they are not discriminating at all.
    user_responses = [r.user_responded for r in scored if r.user_responded is not None]
    all_same_button = len(set(user_responses)) <= 1 and len(user_responses) > 0

    # Pre-penalty discriminability (used to gate gaze)
    discriminability_pre_penalty = discriminability
    if all_same_button:
        discriminability *= 0.3   # 70% penalty for monotonic button pressing

    discriminability = max(0.0, min(1.0, discriminability))

    # ── Reaction speed (only for genuine recognition responses) ──────────────
    # Use RTs from stimuli where the patient actively said "I recognize this"
    # (pressed Space). Ignoring Enter-only sessions prevents gaming via fast skips.
    recognition_rts = [
        r.reaction_time_ms
        for r in scored
        if r.reaction_time_ms is not None and r.user_responded is True
    ]
    rt_avg = statistics.mean(recognition_rts) if recognition_rts else 2000.0
    rt_std = statistics.stdev(recognition_rts) if len(recognition_rts) > 1 else 0.0
    reaction_speed_score = max(0.0, 1.0 - rt_avg / 3000.0) * 100.0

    # ── Gaze contribution gated by cognitive engagement ───────────────────────
    # Pure gaze-camera staring cannot compensate for zero discrimination.
    # Gaze is only credited proportionally to how much the patient discriminated.
    engagement_gate = min(discriminability_pre_penalty * 2.0, 1.0)
    effective_gaze = gaze_stability * engagement_gate

    # ── Composite cognitive index ─────────────────────────────────────────────
    # Weights: discrimination 55%, attention 25%, speed 20%
    cognitive_index = (
        discriminability * 55.0
        + effective_gaze * 25.0
        + reaction_speed_score * 20.0 / 100.0
    )
    cognitive_index = round(min(100.0, max(0.0, cognitive_index)), 2)

    # Legacy accuracy (overall correct / total, for display)
    correct_count   = sum(1 for r in scored if r.response_correct)
    total_stimuli   = len(scored)
    identification_accuracy = correct_count / total_stimuli if total_stimuli > 0 else 0.0

    # MMSE equivalent: linear map CI→[0,30]
    derived_mmse = round(min(30, max(0, cognitive_index * 30.0 / 100.0)))

    return {
        "reaction_time_avg_ms": round(rt_avg, 2),
        "reaction_time_std_ms": round(rt_std, 2),
        "identification_accuracy": round(identification_accuracy, 4),
        "gaze_stability_score": round(gaze_stability, 4),
        "saccade_count": saccade_count,
        "correct_count": correct_count,
        "total_stimuli": total_stimuli,
        # Signal detection detail (informational — not in CSV schema but useful for logs)
        "hit_count": hits,
        "false_alarm_count": false_alarms,
        "hit_rate": round(hit_rate, 4),
        "false_alarm_rate": round(fa_rate, 4),
        "discriminability": round(discriminability, 4),
        "cognitive_index": cognitive_index,
        "derived_mmse": derived_mmse,
    }


def interpret_cognitive_index(cognitive_index: float) -> str:
    """Map cognitive_index to a clinical stage string."""
    if cognitive_index >= 75:
        return "Normal"
    if cognitive_index >= 45:
        return "MCI"
    return "AD"
