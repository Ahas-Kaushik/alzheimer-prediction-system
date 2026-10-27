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


def _gaussian_kernel(ksize: int, sigma: float, dtype, device) -> torch.Tensor:
    x = torch.linspace(-(ksize // 2), ksize // 2, ksize, dtype=dtype, device=device)
    g = torch.exp(-x.pow(2) / (2 * sigma ** 2))
    g = g / g.sum()
    return (g.unsqueeze(0) * g.unsqueeze(1)).view(1, 1, ksize, ksize)


def _physics_fallback_pet(mri_tensor: torch.Tensor) -> torch.Tensor:
    """Approximate an FDG-PET uptake map from a T1-weighted MRI.

    FDG uptake follows tissue, not raw pixel brightness:
      outside the head  -> no uptake
      CSF / ventricles  -> near zero (darkest brain tissue on T1)
      gray matter       -> high uptake (cortex and deep gray)
      white matter      -> about 40% of gray-matter uptake (brightest brain on T1)

    Thresholds are percentiles inside each scan's own brain mask, because
    OASIS JPEGs are not in a fixed T1 intensity range. Uptake stays on a
    fixed 0–1 scale so background is not stretched into false hot spots.
    """
    x = mri_tensor.float()
    if x.dim() == 3:
        x = x.unsqueeze(0)
    device, dtype = x.device, x.dtype
    t = ((x + 1.0) / 2.0).clamp(0.0, 1.0)
    k_pre = _gaussian_kernel(9, 2.0, dtype, device)
    smoothed = F.conv2d(t, k_pre, padding=4)

    pet = torch.zeros_like(smoothed)
    brain = torch.zeros_like(smoothed)
    for i in range(smoothed.shape[0]):
        img = smoothed[i, 0]
        border = torch.cat([img[0], img[-1], img[:, 0], img[:, -1]])
        bg = border.median()
        mask = img > (bg + 0.06)
        if int(mask.sum()) < 64:
            continue
        vals = img[mask]
        csf_cut = torch.quantile(vals, 0.18)
        wm_cut = torch.quantile(vals, 0.62)
        uptake = torch.zeros_like(img)
        csf = mask & (img <= csf_cut)
        gm = mask & (img > csf_cut) & (img <= wm_cut)
        wm = mask & (img > wm_cut)
        uptake[csf] = 0.05
        span = (wm_cut - csf_cut).clamp(min=1e-4)
        uptake[gm] = 1.0 - 0.22 * ((img[gm] - csf_cut) / span)
        uptake[wm] = 0.40
        pet[i, 0] = uptake
        brain[i, 0] = mask.float()

    k_post = _gaussian_kernel(11, 2.2, dtype, device)
    pet = F.conv2d(pet, k_post, padding=5)
    pet = pet * (F.conv2d(brain, k_post, padding=5) > 0.35).float()
    return (pet.clamp(0.0, 1.0) * 2.0 - 1.0)


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
    """FDG-style activity map for display.

    The GAN was trained on 24 brain-tumor MRI/PET pairs, so its colors do not
    follow cortical glucose uptake. The displayed heatmap uses the same
    tissue uptake map as detection: cortex high, white matter moderate,
    ventricles and background dark.

    Args:
        mri_tensor: Shape (1, 1, 256, 256) with values in [-1, 1].

    Returns:
        Uptake tensor of the same shape, values in [-1, 1].
    """
    device = _resolve_device()
    return _physics_fallback_pet(mri_tensor.to(device)).cpu()
