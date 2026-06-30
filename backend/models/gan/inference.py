"""Load a trained GAN generator checkpoint and run inference on a single MRI tensor.

If no trained checkpoint exists, falls back to a physics-based pseudo-PET
(tissue-class intensity mapping + light blur) so the frontend remains
functional while the model is being trained.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F

from backend.config import settings
from backend.models.gan.generator import LightweightUNetGenerator
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_generator: Optional[LightweightUNetGenerator] = None
_device: Optional[torch.device] = None
_using_fallback: bool = False


def _resolve_device() -> torch.device:
    if settings.gan_inference_device == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_generator(checkpoint_path: Optional[str | Path] = None) -> LightweightUNetGenerator:
    """Load the generator from a checkpoint file (lazy singleton).

    Falls back to physics-based pseudo-PET if no checkpoint exists.
    """
    global _generator, _device, _using_fallback

    if _generator is not None:
        return _generator

    _device = _resolve_device()
    _generator = LightweightUNetGenerator().to(_device)

    ckpt = Path(checkpoint_path or settings.gan_checkpoint_path)
    if ckpt.exists():
        state = torch.load(str(ckpt), map_location=_device, weights_only=True)
        if "generator" in state:
            state = state["generator"]
        _generator.load_state_dict(state)
        _using_fallback = False
        logger.info(f"GAN generator loaded from {ckpt}")
    else:
        _using_fallback = True
        logger.warning(
            f"No GAN checkpoint at {ckpt}. Using physics-based pseudo-PET fallback. "
            "Train the model with: python -m backend.models.gan.train --cuda"
        )

    _generator.eval()
    return _generator


def _physics_fallback_pet(mri_tensor: torch.Tensor) -> torch.Tensor:
    """Generate a pseudo-PET from MRI using tissue-specific intensity mapping.

    Approximates FDG-PET metabolic activity from T1 structural MRI by
    assigning realistic uptake values per tissue class:

      Background / air  (T1 < -0.90)    ->  0.00  (no uptake)
      CSF / ventricles  (T1: 0.00-0.12) ->  0.05  (near zero)
      Gray matter       (T1: 0.12-0.60) ->  0.70-1.00 (peak FDG uptake)
      White matter      (T1: 0.60-0.85) ->  0.40-0.55 (moderate uptake)
      Bone / scalp      (T1 > 0.85)     ->  0.10  (low uptake)

    The result is lightly smoothed to simulate PET's lower resolution
    and normalized to [-1, 1] for pipeline consistency.
    """
    device = mri_tensor.device
    arr = mri_tensor.clone().float()   # (1, 1, H, W) in [-1, 1]

    # ── Step 1: Blur MRI FIRST to remove isolated noisy pixels ───────────────
    # This prevents single-pixel GM-range noise in WM regions from appearing
    # as isolated red dots after tissue classification.
    ksize_pre = 11
    sigma_pre = 3.0
    x = torch.linspace(-(ksize_pre // 2), ksize_pre // 2, ksize_pre, dtype=arr.dtype, device=device)
    g = torch.exp(-x.pow(2) / (2 * sigma_pre ** 2))
    g = g / g.sum()
    k_pre = (g.unsqueeze(0) * g.unsqueeze(1)).view(1, 1, ksize_pre, ksize_pre).to(device)
    smoothed = F.conv2d(arr, k_pre, padding=ksize_pre // 2)

    # ── Step 2: Tissue-class activity mapping on smoothed image ──────────────
    t = (smoothed + 1.0) / 2.0   # [-1,1] -> [0,1]
    pet = torch.zeros_like(t)

    # CSF / ventricles (T1 ≈ 0.00–0.12): near-zero uptake
    pet[(t >= 0.00) & (t < 0.12)] = 0.05

    # Gray matter (T1 ≈ 0.12–0.60): peak FDG uptake, smooth triangular profile
    mask_gm = (t >= 0.12) & (t < 0.60)
    gm_val = t[mask_gm]
    pet[mask_gm] = torch.where(
        gm_val < 0.35,
        0.65 + (gm_val - 0.12) / (0.35 - 0.12) * 0.35,   # 0.65 → 1.00
        1.00 - (gm_val - 0.35) / (0.60 - 0.35) * 0.40,   # 1.00 → 0.60
    )

    # White matter (T1 ≈ 0.60–0.85): moderate uptake
    mask_wm = (t >= 0.60) & (t < 0.85)
    pet[mask_wm] = 0.55 - (t[mask_wm] - 0.60) / (0.85 - 0.60) * 0.20   # 0.55 → 0.35

    # Bone / scalp (T1 ≥ 0.85): low uptake
    pet[t >= 0.85] = 0.12

    # Hard background suppression (MRI < -0.88 = very dark pixels)
    pet[arr < -0.88] = 0.0

    # ── Step 3: Second light blur to simulate PET's lower resolution ─────────
    ksize_post = 7
    sigma_post = 1.5
    x2 = torch.linspace(-(ksize_post // 2), ksize_post // 2, ksize_post, dtype=arr.dtype, device=device)
    g2 = torch.exp(-x2.pow(2) / (2 * sigma_post ** 2))
    g2 = g2 / g2.sum()
    k_post = (g2.unsqueeze(0) * g2.unsqueeze(1)).view(1, 1, ksize_post, ksize_post).to(device)
    pet = F.conv2d(pet, k_post, padding=ksize_post // 2)

    # Re-suppress background after blur
    pet[arr < -0.88] = 0.0

    # ── Step 4: Normalize to [-1, 1] ─────────────────────────────────────────
    vmin, vmax = pet.min(), pet.max()
    if vmax > vmin:
        pet = (pet - vmin) / (vmax - vmin) * 2.0 - 1.0
    else:
        pet = torch.zeros_like(pet)

    return pet


def is_using_fallback() -> bool:
    """Always True — physics-based PET is used for detection pipeline."""
    return True


@torch.no_grad()
def synthesize_pet(mri_tensor: torch.Tensor) -> torch.Tensor:
    """Physics-based PET synthesis — always used for the detection pipeline.

    Keeps the tissue-density model as the detection source so that GAN
    artifacts from the small training dataset cannot corrupt the classifier.

    Args:
        mri_tensor: Shape (1, 1, 256, 256) with values in [-1, 1].

    Returns:
        Physics-based pseudo-PET tensor of same shape, values in [-1, 1].
    """
    device = _resolve_device()
    mri_tensor = mri_tensor.to(device)
    return _physics_fallback_pet(mri_tensor).cpu()


@torch.no_grad()
def generate_activity_heatmap(mri_tensor: torch.Tensor) -> torch.Tensor:
    """GAN-based brain activity heatmap — used for visualization only.

    Runs the trained GAN generator to produce a synthetic PET-like tensor
    that captures relative activity patterns learned from real MRI/PET pairs.
    The output is intended for display as a colorized heatmap overlay alongside
    the MRI in the scan comparison view.  It is NOT used in the detection pipeline.

    Args:
        mri_tensor: Shape (1, 1, 256, 256) with values in [-1, 1].

    Returns:
        GAN output tensor of same shape, values in [-1, 1].
        Falls back to physics-based output if the GAN checkpoint is missing.
    """
    global _device

    gen = load_generator()

    if _device is None:
        _device = _resolve_device()

    mri_tensor = mri_tensor.to(_device)
    gen.eval()

    if _using_fallback:
        # Checkpoint missing — use physics as the heatmap source too
        logger.warning("GAN checkpoint missing — heatmap will use physics fallback")
        return _physics_fallback_pet(mri_tensor).cpu()

    return gen(mri_tensor).cpu()
