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
OBJECT_NAMES = ["apple", "clock", "chair", "tree", "phone", "book", "car", "cup", "dog", "hat"]
WORD_NAMES = ["HOUSE", "BREAD", "WATER", "LIGHT", "MUSIC"]

# ── Foils: nonsense/unfamiliar items the patient should NOT respond to ───────
# These are plausible-looking pseudowords that a healthy person can easily
# recognise as "not a real word". An impaired patient may falsely recognise them.
FOIL_WORDS = ["ZARVEX", "QUELBIN", "FLOXID", "SNELDAR", "BRIXON"]
FOIL_OBJECTS = ["zarvex", "quelbin", "floxid"]   # shown as labels (no images)

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
    n_target_objects: int = 4,
    n_target_words: int = 3,
    n_foils: int = 3,
    duration_ms: int = 3000,
    n_warmup: int = 2,
    seed: Optional[int] = None,
    # Legacy aliases kept for backward-compat with any direct callers
    n_objects: Optional[int] = None,
    n_words: Optional[int] = None,
) -> list[Stimulus]:
    """Build a randomized stimulus list: warmup → targets → foils (interleaved).

    Total scored stimuli = n_target_objects + n_target_words + n_foils = 10.
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

    # Build foil stimuli
    n_foil_words = min(n_foils, len(FOIL_WORDS))
    n_foil_objects = max(0, n_foils - n_foil_words)
    foil_word_samples = rng.sample(FOIL_WORDS, n_foil_words)
    foil_obj_samples = rng.sample(FOIL_OBJECTS, min(n_foil_objects, len(FOIL_OBJECTS)))

    foil_items: list[tuple[str, str, bool]] = (
        [("foil", w, False) for w in foil_word_samples] +
        [("foil", o, False) for o in foil_obj_samples]
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


def create_result(stimulus: Stimulus, shown_at: float) -> StimulusResult:
    return StimulusResult(
        stimulus=stimulus,
        shown_at=shown_at,
        responded_at=None,
        response_correct=None,
        reaction_time_ms=None,
        user_responded=None,
    )


def record_response(result: StimulusResult, user_responded: bool) -> StimulusResult:
    """Record the patient's button press and score it objectively.

    user_responded=True  means the patient pressed Space ("I recognize this").
    user_responded=False means the patient pressed Enter or timed out ("I don't recognize this").

    Correct response:
    - Target  + Space  → hit (correct)
    - Target  + Enter  → miss (incorrect)
    - Foil    + Enter  → correct rejection (correct)
    - Foil    + Space  → false alarm (incorrect)
    """
    now = time.time()
    result.responded_at = now
    result.user_responded = user_responded
    # response_correct = True when the action matches what the stimulus calls for
    result.response_correct = (user_responded == result.stimulus.is_target)
    result.reaction_time_ms = (now - result.shown_at) * 1000.0
    return result
