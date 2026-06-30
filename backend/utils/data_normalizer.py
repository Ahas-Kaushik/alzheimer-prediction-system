from __future__ import annotations

import numpy as np


# Reference ranges for z-score normalization of clinical features.
# Values derived from published ADNI population statistics.
_CLINICAL_STATS: dict[str, tuple[float, float]] = {
    # (mean, std)
    "age": (72.0, 7.5),
    "education_years": (15.0, 3.0),
    "mmse_score": (25.0, 4.5),
    "moca_score": (24.0, 5.0),
    "cdr_score": (0.5, 0.5),
    "amyloid_beta_42": (1000.0, 350.0),
    "tau_protein": (280.0, 160.0),
    "p_tau_181": (25.0, 15.0),
    "hemoglobin": (13.5, 1.5),
    "glucose_fasting": (100.0, 20.0),
    "cholesterol_total": (195.0, 35.0),
    "hdl": (55.0, 15.0),
    "ldl": (115.0, 30.0),
    "triglycerides": (130.0, 60.0),
    "vitamin_b12": (450.0, 200.0),
    "thyroid_tsh": (2.0, 1.5),
    "hippocampal_volume": (3.5, 0.6),
    "cortical_thickness": (2.75, 0.25),
    "wmh_volume": (5.0, 8.0),
}

_BOOLEAN_FIELDS = {
    "smoking_history",
    "diabetes",
    "hypertension",
    "depression_history",
    "family_history_ad",
}

_CATEGORICAL_ENCODINGS: dict[str, dict[str, float]] = {
    "gender": {"male": 0.0, "female": 1.0, "other": 0.5},
    "apoe4_status": {"negative": 0.0, "positive": 1.0, "unknown": 0.5, "carrier": 1.0},
}


# Field name aliases: frontend form keys → normalizer canonical keys.
# Allows the hybrid ClinicalDataForm to use short names without breaking the pipeline.
_FIELD_ALIASES: dict[str, str] = {
    "amyloid_level": "amyloid_beta_42",
    "tau_level": "tau_protein",
    "ptau_level": "p_tau_181",
    "glucose": "glucose_fasting",
    "cholesterol": "cholesterol_total",
    "vit_b12": "vitamin_b12",
    "tsh": "thyroid_tsh",
    "smoking": "smoking_history",
    "depression": "depression_history",
    "apoe4_status": "apoe4_status",  # kept as-is but normalised below
}


def _remap_fields(raw: dict) -> dict:
    """Remap frontend form field names to canonical normalizer field names."""
    out = {}
    for k, v in raw.items():
        canonical = _FIELD_ALIASES.get(k, k)
        out[canonical] = v
    return out


def normalize_clinical_features(raw: dict) -> list[float]:
    """Convert a raw clinical feature dict to a normalized float vector.

    Accepts both canonical field names and frontend form aliases.
    Missing optional fields are imputed with 0.0 (mean after z-score).

    Args:
        raw: Dict with clinical field names as keys (canonical or aliased).

    Returns:
        Ordered list of floats ready for model input.
    """
    raw = _remap_fields(raw)
    vector: list[float] = []

    for field, (mean, std) in _CLINICAL_STATS.items():
        val = raw.get(field)
        if val is None:
            vector.append(0.0)
        else:
            z = (float(val) - mean) / (std + 1e-8)
            vector.append(float(np.clip(z, -3.0, 3.0)))

    for field in _BOOLEAN_FIELDS:
        val = raw.get(field)
        vector.append(1.0 if val else 0.0)

    for field, mapping in _CATEGORICAL_ENCODINGS.items():
        val = str(raw.get(field, "unknown")).lower()
        vector.append(mapping.get(val, 0.5))

    return vector


def normalize_cognitive_scores(scores: dict) -> list[float]:
    """Normalize cognitive test output scores to a fixed-length float vector.

    Returns an 8-element vector matching Agent 1's expected input dimensions.
    """
    def _clamp01(v: float | None, default: float = 0.5) -> float:
        if v is None:
            return default
        return float(np.clip(v, 0.0, 1.0))

    reaction_speed = max(0.0, 1.0 - (scores.get("reaction_time_avg_ms", 1500) / 3000.0))
    reaction_std_norm = 1.0 - min(scores.get("reaction_time_std_ms", 500) / 2000.0, 1.0)
    accuracy = _clamp01(scores.get("identification_accuracy"))
    gaze = _clamp01(scores.get("gaze_stability_score"))
    saccade_norm = 1.0 - min(scores.get("saccade_count", 20) / 50.0, 1.0)
    correct_ratio = _clamp01(
        scores.get("correct_count", 0) / max(scores.get("total_stimuli", 10), 1)
    )
    cognitive_index_norm = _clamp01(scores.get("cognitive_index", 50) / 100.0)

    return [
        reaction_speed,
        reaction_std_norm,
        accuracy,
        gaze,
        saccade_norm,
        correct_ratio,
        cognitive_index_norm,
        cognitive_index_norm,  # duplicate as 8th dim for symmetry with spec
    ]
