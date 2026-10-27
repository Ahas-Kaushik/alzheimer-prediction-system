"""Agent 2 — Brain Imaging Synthesis Agent.

Accepts a preprocessed MRI tensor, runs GAN inference to produce a synthetic
PET tensor, saves the result as a PNG, and returns the tensor + quality metrics.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import torch

from backend.config import settings
from backend.models.gan.inference import generate_activity_heatmap, is_using_fallback, synthesize_pet
from backend.utils.image_utils import compute_psnr, compute_ssim, save_pet_as_colored_png
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def refresh_saved_pet(mri_path: str, pet_path: str) -> str | None:
    """Rewrite a stored PET PNG with the current tissue-uptake map.

    Older visits kept a PET file from the previous color mapping. Loading the
    MRI again and saving over ``pet_path`` makes the prediction page and the
    PDF use the same image the classifier's PET features come from.
    """
    try:
        from backend.utils.image_utils import load_mri_image, save_pet_as_colored_png

        mri = load_mri_image(mri_path, size=settings.gan_image_size)
        pet = synthesize_pet(mri)
        dest = Path(pet_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        save_pet_as_colored_png(pet, dest)
        return str(dest)
    except Exception as exc:
        logger.warning(f"Could not refresh PET image: {exc}")
        return None


def run(
    mri_tensor: torch.Tensor,
    patient_id: str,
    scan_id: str,
    real_pet_tensor: Optional[torch.Tensor] = None,
) -> dict:
    """Synthesize PET images from an MRI tensor and persist the results.

    Two outputs are generated:
      - pet_synthetic.png  : physics-based PET (used by classifier for prediction)
      - activity_heatmap.png : GAN-based output (visualization only, not used in detection)

    Args:
        mri_tensor: Shape (1, 1, 256, 256), values in [-1, 1].
        patient_id: Used to construct the output directory path.
        scan_id: Used to name the output files.
        real_pet_tensor: Optional ground-truth PET for metric computation.

    Returns:
        Dict with keys: pet_tensor, file_path, heatmap_file_path,
                        ssim_score, psnr_score, is_fallback.
    """
    logger.info(f"Agent2: synthesizing PET for patient={patient_id} scan={scan_id}")

    # ── Physics-based PET (used for detection) ────────────────────────────────
    pet_tensor = synthesize_pet(mri_tensor)

    out_dir = settings.upload_path / patient_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pet_png = out_dir / f"{scan_id}_pet_synthetic.png"
    save_pet_as_colored_png(pet_tensor, pet_png)

    # ── GAN activity heatmap (visualization only) ─────────────────────────────
    heatmap_png: Optional[str] = None
    try:
        heatmap_tensor = generate_activity_heatmap(mri_tensor)
        heatmap_path = out_dir / f"{scan_id}_activity_heatmap.png"
        save_pet_as_colored_png(heatmap_tensor, heatmap_path)
        heatmap_png = str(heatmap_path)
        logger.info(f"Agent2: activity heatmap saved → {heatmap_path}")
    except Exception as e:
        logger.warning(f"Agent2: heatmap generation failed (non-critical): {e}")

    # ── Optional quality metrics ──────────────────────────────────────────────
    ssim_score: Optional[float] = None
    psnr_score: Optional[float] = None
    if real_pet_tensor is not None:
        try:
            ssim_score = compute_ssim(real_pet_tensor, pet_tensor)
            psnr_score = compute_psnr(real_pet_tensor, pet_tensor)
        except Exception as e:
            logger.warning(f"Metric computation failed: {e}")

    logger.info(
        f"Agent2 done: pet_path={pet_png}, heatmap={heatmap_png}, "
        f"ssim={ssim_score}, psnr={psnr_score}"
    )
    return {
        "pet_tensor": pet_tensor,
        "file_path": str(pet_png),
        "heatmap_file_path": heatmap_png,
        "ssim_score": ssim_score,
        "psnr_score": psnr_score,
        "is_fallback": is_using_fallback(),
    }
