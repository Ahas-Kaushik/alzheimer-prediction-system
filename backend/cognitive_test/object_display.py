"""Manages the stimulus sequence for the cognitive test session.

Stimuli include real everyday items (targets) and nonsense/unfamiliar items
(foils). Patients should respond ONLY to targets. This allows proper signal
detection scoring (hits vs false alarms) rather than simple button-press counting.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

# ── Targets: common everyday items the patient SHOULD recognize ──────────────
OBJECT_NAMES = [
    "apple", "clock", "chair", "tree", "phone", "book", "car", "cup", "dog", "hat",
    "spoon", "flower", "key", "shoe", "table", "bird", "bottle", "pencil",
]
WORD_NAMES = [
    "HOUSE", "BREAD", "WATER", "LIGHT", "MUSIC",
    "RIVER", "TABLE", "GARDEN", "WINDOW", "MARKET", "SILVER", "CANDLE",
]

# ── Foils: nonsense/unfamiliar items the patient should NOT respond to ───────
# Two difficulty tiers so the test genuinely requires reading, not pattern-mashing:
#   * pseudowords   — plausible but clearly not real words.
#   * near-words    — real words with a single altered letter. These are HARD:
#                     a person who is not actually reading will false-alarm on them.
FOIL_WORDS = ["ZARVEX", "QUELBIN", "FLOXID", "SNELDAR", "BRIXON", "TRUVOND", "GLIMPER", "PLENDA"]
FOIL_NEAR_WORDS = ["HOWSE", "BREADT", "WATTER", "LIGHNT", "MUSIQ", "RIVVER", "TABEL", "WINDOE"]
FOIL_OBJECTS = ["zarvex", "quelbin", "floxid", "brundle", "snorate"]   # shown as labels (no images)

ASSETS_DIR = Path(__file__).parent / "assets"
OBJECTS_DIR = ASSETS_DIR / "objects"
WORDS_FILE = ASSETS_DIR / "words" / "words.txt"


@dataclass
class Stimulus:
    index: int
    kind: Literal["object", "word", "foil"]
    label: str
    image_path: Optional[str]
    duration_ms: int
    is_warmup: bool = False
    is_target: bool = True   # False for foil stimuli


def build_stimulus_sequence(
    n_target_objects: int = 6,
    n_target_words: int = 3,
    n_foils: int = 4,
    duration_ms: int = 2200,
    n_warmup: int = 2,
    seed: Optional[int] = None,
    # Legacy aliases kept for backward-compat with any direct callers
    n_objects: Optional[int] = None,
    n_words: Optional[int] = None,
) -> list[Stimulus]:
    """Build a randomized stimulus list: warmup → targets → foils (interleaved).

    Default total scored stimuli = 6 + 3 + 4 = 13 (tougher 10–15 item test).
    The reset flow requests ~20 items via larger counts. Roughly half the foils
    are hard "near-words" (real word with one altered letter) so the task cannot
    be passed by pattern-mashing without actually reading each item.
    """
    # Legacy param handling
    if n_objects is not None:
        n_target_objects = n_objects - 1   # one fewer object to make room for foils
    if n_words is not None:
        n_target_words = n_words - 2

    rng = random.Random(seed)

    # Build target stimuli
    objects = rng.sample(OBJECT_NAMES, min(n_target_objects, len(OBJECT_NAMES)))
    words = rng.sample(WORD_NAMES, min(n_target_words, len(WORD_NAMES)))

    target_items: list[tuple[str, str, bool]] = (
        [("object", name, True) for name in objects] +
        [("word", name, True) for name in words]
    )

    # Build foil stimuli — split between pseudowords and hard near-words.
    n_near = n_foils // 2
    n_pseudo = n_foils - n_near
    pseudo_pool = FOIL_WORDS + FOIL_OBJECTS
    near_samples = rng.sample(FOIL_NEAR_WORDS, min(n_near, len(FOIL_NEAR_WORDS)))
    pseudo_samples = rng.sample(pseudo_pool, min(n_pseudo, len(pseudo_pool)))

    foil_items: list[tuple[str, str, bool]] = (
        [("foil", w, False) for w in near_samples] +
        [("foil", w, False) for w in pseudo_samples]
    )

    all_items = target_items + foil_items
    rng.shuffle(all_items)

    scored: list[Stimulus] = []
    for i, (kind, label, is_target) in enumerate(all_items):
        img_path = None
        if kind == "object":
            candidate = OBJECTS_DIR / f"{label}.png"
            img_path = str(candidate) if candidate.exists() else None
        scored.append(Stimulus(
            index=i,
            kind=kind,
            label=label,
            image_path=img_path,
            duration_ms=duration_ms,
            is_warmup=False,
            is_target=is_target,
        ))

    # Warmup — always targets so patient learns the pattern
    warmup_labels = [("object", "apple", True), ("word", "HOUSE", True)]
    warmup: list[Stimulus] = []
    for i, (kind, label, is_target) in enumerate(warmup_labels[:n_warmup]):
        img_path = None
        if kind == "object":
            candidate = OBJECTS_DIR / f"{label}.png"
            img_path = str(candidate) if candidate.exists() else None
        warmup.append(Stimulus(
            index=-(n_warmup - i),
            kind=kind,
            label=label,
            image_path=img_path,
            duration_ms=duration_ms,
            is_warmup=True,
            is_target=is_target,
        ))

    return warmup + scored


@dataclass
class StimulusResult:
    stimulus: Stimulus
    shown_at: float
    responded_at: Optional[float]
    response_correct: Optional[bool]   # True = hit or correct rejection; False = miss or false alarm
    reaction_time_ms: Optional[float]
    user_responded: Optional[bool] = None   # True = pressed Space (recognized); False = Enter/timeout
    gaze_on_screen: Optional[bool] = None    # was the patient actually looking at the stimulus?


def create_result(stimulus: Stimulus, shown_at: float) -> StimulusResult:
    return StimulusResult(
        stimulus=stimulus,
        shown_at=shown_at,
        responded_at=None,
        response_correct=None,
        reaction_time_ms=None,
        user_responded=None,
        gaze_on_screen=None,
    )


def record_response(
    result: StimulusResult,
    user_responded: bool,
    reaction_time_ms: Optional[float] = None,
) -> StimulusResult:
    """Record the patient's button press and score it objectively.

    user_responded=True  means the patient pressed Space ("I recognize this").
    user_responded=False means the patient pressed Enter or timed out ("I don't recognize this").

    Correct response:
    - Target  + Space  → hit (correct)
    - Target  + Enter  → miss (incorrect)
    - Foil    + Enter  → correct rejection (correct)
    - Foil    + Space  → false alarm (incorrect)

    reaction_time_ms: the browser-measured time from stimulus onset to keypress.
    When not provided we fall back to a server-side estimate (less accurate,
    kept only for direct callers/tests).
    """
    now = time.time()
    result.responded_at = now
    result.user_responded = user_responded
    # response_correct = True when the action matches what the stimulus calls for
    result.response_correct = (user_responded == result.stimulus.is_target)
    if reaction_time_ms is not None and reaction_time_ms >= 0:
        result.reaction_time_ms = float(reaction_time_ms)
    else:
        result.reaction_time_ms = (now - result.shown_at) * 1000.0
    return result
