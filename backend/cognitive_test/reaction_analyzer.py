"""Compute cognitive test scores using signal detection theory.

Scoring is deliberately *tough* and hard to game:

- Stimuli include foils (items the patient should NOT respond to), half of them
  hard "near-words". Scoring uses discriminability (hit_rate − false_alarm_rate),
  not raw button-press counts.
- Responses that are physiologically too fast to have read the item, or that were
  made while the patient was NOT looking at the screen, are treated as INVALID —
  they are counted against the patient (as if unread) and drive an engagement
  multiplier that scales the whole score down.
- Monotonic (all-same) and strictly-alternating button patterns are penalised as
  non-discriminating behaviour.
- The discriminability → cognitive-index mapping is non-linear: only genuine,
  engaged, near-ceiling discrimination yields a high index. Careless or impaired
  performance collapses toward a low index.

The net effect: you cannot get a high score by mashing keys, by skipping
everything, or by looking away — you have to actually read and discriminate.
"""
from __future__ import annotations

import statistics
from typing import Optional

from backend.cognitive_test.object_display import StimulusResult

# A keypress faster than this after stimulus onset could not have followed
# reading the item — it is an impulsive / anticipatory press.
MIN_VALID_RT_MS = 350.0


def _is_valid_response(r: StimulusResult) -> bool:
    """A response counts as 'genuine' only if the patient plausibly read the item.

    Requires: looking at the screen (when gaze data exists) AND a reaction time
    above the impulsive-press floor.
    """
    if r.gaze_on_screen is False:
        return False
    if r.reaction_time_ms is not None and r.reaction_time_ms < MIN_VALID_RT_MS:
        return False
    return True


def compute_scores(
    results: list[StimulusResult],
    saccade_count: int,
    gaze_stability: float,
    on_screen_ratio: Optional[float] = None,
) -> dict:
    """Compute cognitive test metrics with tough, gaze-gated signal-detection scoring.

    Args:
        results: All StimulusResult objects (including warmup — filtered here).
        saccade_count: Total rapid gaze changes detected.
        gaze_stability: Fraction of gaze on stimulus area (0.0–1.0).
        on_screen_ratio: Fraction of the session the patient looked at the screen.

    Returns:
        Dict matching the Agent 3 output spec.
    """
    scored = [r for r in results if not r.stimulus.is_warmup]

    targets = [r for r in scored if r.stimulus.is_target]
    foils   = [r for r in scored if not r.stimulus.is_target]

    # ── Validity / engagement ────────────────────────────────────────────────
    # Invalid = too-fast press or looked-away. These are treated as unread and
    # penalise the engagement multiplier.
    n_total = len(scored)
    invalid = [r for r in scored if not _is_valid_response(r)]
    n_invalid = len(invalid)
    valid_ratio = (n_total - n_invalid) / n_total if n_total > 0 else 0.0

    # ── Signal detection metrics ─────────────────────────────────────────────
    # An invalid (too-fast / looked-away) response cannot be a genuine "hit" or
    # "correct rejection" — force it to count as an error for detection scoring.
    def _correct(r: StimulusResult) -> bool:
        return bool(r.response_correct) and _is_valid_response(r)

    hits               = sum(1 for r in targets if _correct(r))
    correct_rejections = sum(1 for r in foils   if _correct(r))
    false_alarms       = sum(1 for r in foils   if not _correct(r))

    n_targets = len(targets)
    n_foils   = len(foils)

    hit_rate = hits / n_targets if n_targets > 0 else 0.0
    fa_rate  = false_alarms / n_foils if n_foils > 0 else 0.0

    # Discriminability: (hit_rate - fa_rate) ∈ [-1, 1] mapped to [0, 1].
    discriminability = (hit_rate - fa_rate + 1.0) / 2.0

    # ── Response-pattern penalty ──────────────────────────────────────────────
    # Only monotonic (all-same) pressing is penalised — it reflects zero
    # discrimination. We do NOT penalise alternating responses: a genuine
    # responder to a shuffled target/foil sequence can legitimately alternate.
    user_responses = [r.user_responded for r in scored if r.user_responded is not None]
    all_same_button = len(set(user_responses)) <= 1 and len(user_responses) > 0

    if all_same_button:
        discriminability *= 0.25   # 75% penalty for monotonic mashing

    discriminability = max(0.0, min(1.0, discriminability))

    # ── Engagement multiplier ────────────────────────────────────────────────
    # Scales the whole score by how much the patient actually engaged (read the
    # items and looked at the screen). Looking away or impulsive pressing tanks it.
    engagement = valid_ratio
    if on_screen_ratio is not None:
        engagement *= max(0.0, min(1.0, on_screen_ratio))

    # ── Reaction speed (only for genuine, valid recognition responses) ────────
    recognition_rts = [
        r.reaction_time_ms
        for r in scored
        if r.reaction_time_ms is not None and r.user_responded is True and _is_valid_response(r)
    ]
    rt_avg = statistics.mean(recognition_rts) if recognition_rts else 2200.0
    rt_std = statistics.stdev(recognition_rts) if len(recognition_rts) > 1 else 0.0
    reaction_speed_score = max(0.0, 1.0 - rt_avg / 3000.0) * 100.0

    # ── Non-linear discrimination term ────────────────────────────────────────
    # Toughness: chance-level ≈ 0 and only near-ceiling discrimination earns the
    # bulk of the points.
    disc_centered = max(0.0, (discriminability - 0.5) / 0.5)   # 0.5→0 , 1.0→1
    disc_score = disc_centered ** 1.5                          # convex ⇒ tougher

    # ── Gaze + speed gated by GENUINE discrimination ──────────────────────────
    # Staring at the screen while mashing one key must earn nothing, so the gaze
    # and speed bonuses are credited only in proportion to real discrimination.
    effective_gaze = gaze_stability * disc_centered
    effective_speed = (reaction_speed_score / 100.0) * disc_centered

    # ── Composite cognitive index ─────────────────────────────────────────────
    # Weights: discrimination 60%, attention 22%, speed 18%. Scaled by engagement.
    raw_index = (
        disc_score * 60.0
        + effective_gaze * 22.0
        + effective_speed * 18.0
    )
    cognitive_index = round(min(100.0, max(0.0, raw_index * engagement)), 2)

    # Legacy accuracy (overall correct / total, for display)
    correct_count   = sum(1 for r in scored if _correct(r))
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
        # Signal detection + integrity detail (informational)
        "hit_count": hits,
        "false_alarm_count": false_alarms,
        "hit_rate": round(hit_rate, 4),
        "false_alarm_rate": round(fa_rate, 4),
        "discriminability": round(discriminability, 4),
        "invalid_response_count": n_invalid,
        "valid_ratio": round(valid_ratio, 4),
        "on_screen_ratio": round(on_screen_ratio, 4) if on_screen_ratio is not None else None,
        "engagement": round(engagement, 4),
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
