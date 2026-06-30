"""Maps Alzheimer's stage + confidence to per-region severity scores.

Region impact table follows Section 9.2 of PROJECT_KNOWLEDGE.md.
"""
from __future__ import annotations

from typing import Literal

AlzheimerStage = Literal["Normal", "MCI", "AD"]

# (base_severity_normal, base_severity_MCI, base_severity_AD)
_REGION_PROFILES: dict[str, tuple[float, float, float]] = {
    "Hippocampus":       (0.05, 0.60, 0.90),
    "Entorhinal Cortex": (0.05, 0.50, 0.80),
    "Temporal Lobe":     (0.05, 0.35, 0.75),
    "Parietal Lobe":     (0.02, 0.20, 0.65),
    "Prefrontal Cortex": (0.02, 0.15, 0.55),
    "Occipital Lobe":    (0.01, 0.08, 0.25),
    "Cerebellum":        (0.01, 0.05, 0.15),
}


def map_regions(stage: AlzheimerStage, confidence: float) -> list[dict]:
    """Build region severity list for the digital twin visualization.

    Args:
        stage: Predicted Alzheimer's stage.
        confidence: Model confidence (0–1). Modulates severity magnitude.

    Returns:
        List of dicts with 'name', 'severity' (0–1), 'status' (stage label).
    """
    stage_idx = {"Normal": 0, "MCI": 1, "AD": 2}[stage]
    regions = []
    for name, (s_norm, s_mci, s_ad) in _REGION_PROFILES.items():
        base = (s_norm, s_mci, s_ad)[stage_idx]
        # Scale severity by confidence — low-confidence predictions are less severe
        severity = round(base * (0.5 + 0.5 * confidence), 4)
        severity = min(1.0, max(0.0, severity))

        if severity < 0.15:
            region_status: AlzheimerStage = "Normal"
        elif severity < 0.55:
            region_status = "MCI"
        else:
            region_status = "AD"

        regions.append({"name": name, "severity": severity, "status": region_status})
    return regions


def compute_neuron_connectivity(stage: AlzheimerStage, confidence: float) -> float:
    """Overall brain connectivity score (0=fully degraded, 1=healthy)."""
    base = {"Normal": 0.92, "MCI": 0.65, "AD": 0.35}[stage]
    return round(base * (0.7 + 0.3 * confidence), 4)
