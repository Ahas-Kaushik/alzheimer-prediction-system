"""Alzheimer's stage classifier: Normal / MCI / AD.

Supports two backends:
  - MLP (3-layer neural network, default for inference)
  - SVM (RBF kernel, trained on the same fused feature vector)

Architecture follows Section 15 of PROJECT_KNOWLEDGE.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import numpy as np
import torch
import torch.nn as nn

STAGES = ["Normal", "MCI", "AD"]

_temperature: Optional[float] = None


def _load_temperature() -> float:
    """Load calibration temperature from checkpoint (defaults to 1.0 if not found)."""
    global _temperature
    if _temperature is not None:
        return _temperature
    try:
        import json
        from backend.config import settings
        t_path = Path(settings.classifier_checkpoint).parent / "temperature.json"
        if t_path.exists():
            with open(t_path) as f:
                _temperature = float(json.load(f)["temperature"])
            return _temperature
    except Exception:
        pass
    _temperature = 1.0
    return _temperature


# ── MLP Classifier ────────────────────────────────────────────────────────────

class AlzheimerMLP(nn.Module):
    """3-layer MLP for Alzheimer's stage classification.

    Input:  fused feature vector [MRI(512) | PET(512) | clinical(N) | cognitive(8)]
    Output: softmax over [Normal, MCI, AD]
    """

    def __init__(self, input_dim: int = 1040):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(128, 3),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


# ── Unified classifier interface ──────────────────────────────────────────────

_mlp_model: Optional[AlzheimerMLP] = None
_svm_model = None


def load_mlp(checkpoint_path: Optional[str | Path] = None, input_dim: int = 1040) -> AlzheimerMLP:
    """Load MLP classifier from checkpoint (lazy singleton)."""
    global _mlp_model
    if _mlp_model is not None:
        return _mlp_model

    _mlp_model = AlzheimerMLP(input_dim=input_dim)

    if checkpoint_path:
        ckpt = Path(checkpoint_path)
        if ckpt.exists():
            state = torch.load(str(ckpt), map_location="cpu")
            if "model_state" in state:
                state = state["model_state"]
            _mlp_model.load_state_dict(state)
        else:
            # No checkpoint: model uses random weights (dev mode)
            pass

    _mlp_model.eval()
    return _mlp_model


def predict_mlp(feature_vector: list[float]) -> dict:
    """Run MLP inference on a fused feature vector.

    Args:
        feature_vector: Concatenated [MRI | PET | clinical | cognitive] floats.

    Returns:
        Dict with 'stage', 'confidence', 'probabilities'.
    """
    from backend.config import settings
    model = load_mlp(
        checkpoint_path=settings.classifier_checkpoint,
        input_dim=len(feature_vector),
    )
    x = torch.tensor(feature_vector, dtype=torch.float32).unsqueeze(0)
    T = _load_temperature()

    with torch.no_grad():
        logits = model(x)
        probs = torch.softmax(logits / T, dim=1).squeeze(0).numpy()

    stage_idx = int(np.argmax(probs))
    return {
        "stage": STAGES[stage_idx],
        "confidence": float(probs[stage_idx]),
        "probabilities": {s: float(p) for s, p in zip(STAGES, probs)},
    }


def predict_svm(feature_vector: list[float]) -> dict:
    """Run SVM inference on a fused feature vector (requires trained .pkl checkpoint)."""
    global _svm_model
    import pickle

    from backend.config import settings
    ckpt = settings.classifier_checkpoint.with_suffix(".pkl")
    if _svm_model is None and ckpt.exists():
        with open(ckpt, "rb") as f:
            _svm_model = pickle.load(f)

    if _svm_model is None:
        # Fallback to MLP if SVM checkpoint unavailable
        return predict_mlp(feature_vector)

    x = np.array(feature_vector).reshape(1, -1)
    stage_idx = int(_svm_model.predict(x)[0])
    probs = _svm_model.predict_proba(x)[0]
    return {
        "stage": STAGES[stage_idx],
        "confidence": float(probs[stage_idx]),
        "probabilities": {s: float(p) for s, p in zip(STAGES, probs)},
    }


def predict(feature_vector: list[float], backend: Literal["mlp", "svm"] = "mlp") -> dict:
    """Unified predict function — routes to MLP or SVM backend."""
    if backend == "svm":
        return predict_svm(feature_vector)
    return predict_mlp(feature_vector)
