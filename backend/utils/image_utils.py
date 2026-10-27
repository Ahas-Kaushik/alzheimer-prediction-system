from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image


def load_mri_image(path: str | Path, size: int = 256) -> torch.Tensor:
    """Load a grayscale MRI image (PNG/JPG/NIfTI) and return a normalized tensor.

    Args:
        path: Filesystem path to the image file.
        size: Target spatial size (square) in pixels.

    Returns:
        Tensor of shape (1, 1, size, size) with values in [-1, 1].
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in {".nii", ".gz"}:
        tensor = _load_nifti(path, size)
    elif suffix == ".dcm":
        tensor = _load_dicom(path, size)
    else:
        tensor = _load_standard_image(path, size)

    return tensor


def _load_standard_image(path: Path, size: int) -> torch.Tensor:
    img = Image.open(path).convert("L")
    img = img.resize((size, size), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = (arr - 0.5) / 0.5  # [0,1] → [-1,1]
    tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)  # (1,1,H,W)
    return tensor


def _load_dicom(path: Path, size: int) -> torch.Tensor:
    try:
        import pydicom
    except ImportError as exc:
        raise ImportError("pydicom is required for DICOM support: pip install pydicom") from exc

    dcm = pydicom.dcmread(str(path))
    pixels = dcm.pixel_array.astype(np.float32)

    # Multi-frame DICOM: pick the middle frame
    if pixels.ndim == 3:
        pixels = pixels[pixels.shape[0] // 2]

    pmin, pmax = pixels.min(), pixels.max()
    if pmax > pmin:
        pixels = (pixels - pmin) / (pmax - pmin)
    else:
        pixels = np.zeros_like(pixels)

    img = Image.fromarray((pixels * 255).astype(np.uint8))
    img = img.resize((size, size), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = (arr - 0.5) / 0.5  # [0, 1] → [-1, 1]
    return torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)


def _load_nifti(path: Path, size: int) -> torch.Tensor:
    try:
        import nibabel as nib
    except ImportError as exc:
        raise ImportError("nibabel is required for NIfTI support") from exc

    nii = nib.load(str(path))
    data = nii.get_fdata().astype(np.float32)

    # Select most informative axial slice (max variance heuristic)
    if data.ndim == 3:
        variances = [np.var(data[:, :, i]) for i in range(data.shape[2])]
        best_slice = int(np.argmax(variances))
        slice_2d = data[:, :, best_slice]
    elif data.ndim == 4:
        slice_2d = data[:, :, data.shape[2] // 2, 0]
    else:
        slice_2d = data

    # Normalize to [0,1] then to [-1,1]
    vmin, vmax = slice_2d.min(), slice_2d.max()
    if vmax > vmin:
        slice_2d = (slice_2d - vmin) / (vmax - vmin)
    else:
        slice_2d = np.zeros_like(slice_2d)

    img = Image.fromarray((slice_2d * 255).astype(np.uint8))
    img = img.resize((size, size), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = (arr - 0.5) / 0.5
    return torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)


def tensor_to_png_bytes(tensor: torch.Tensor) -> bytes:
    """Convert a (1,1,H,W) tensor in [-1,1] to grayscale PNG bytes."""
    import io

    arr = tensor.squeeze().cpu().numpy()
    arr = ((arr + 1.0) / 2.0 * 255).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def tensor_to_pet_png_bytes(tensor: torch.Tensor) -> bytes:
    """Convert a PET tensor (1,1,H,W) in [-1,1] to a colored PNG.

    Uses the clinical hot colormap:
      0.0  → black  (no uptake: air, scalp, ventricles)
      0.4  → red    (low uptake: white matter)
      0.7  → yellow (high uptake: cortex)
      1.0  → white  (peak gray-matter uptake)
    """
    import io

    arr = tensor.squeeze().cpu().float().numpy()
    arr = ((arr + 1.0) / 2.0).clip(0.0, 1.0)

    h, w = arr.shape
    r = np.zeros((h, w), dtype=np.float32)
    g = np.zeros((h, w), dtype=np.float32)
    b = np.zeros((h, w), dtype=np.float32)

    # black → red
    m = arr < 0.45
    t = arr[m] / 0.45
    r[m] = t * 255

    # red → yellow
    m = (arr >= 0.45) & (arr < 0.75)
    t = (arr[m] - 0.45) / 0.30
    r[m] = 255
    g[m] = t * 230

    # yellow → white
    m = arr >= 0.75
    t = (arr[m] - 0.75) / 0.25
    r[m] = 255
    g[m] = 230 + t * 25
    b[m] = t * 255

    rgb = np.stack([r, g, b], axis=-1).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(rgb, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def save_tensor_as_png(tensor: torch.Tensor, out_path: str | Path) -> None:
    """Save a (1,1,H,W) tensor in [-1,1] as a grayscale PNG."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(tensor_to_png_bytes(tensor))


def save_pet_as_colored_png(tensor: torch.Tensor, out_path: str | Path) -> None:
    """Save a PET tensor as a colored PNG using the clinical hot colormap."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(tensor_to_pet_png_bytes(tensor))


def compute_ssim(tensor_a: torch.Tensor, tensor_b: torch.Tensor) -> float:
    """Compute Structural Similarity Index between two (1,1,H,W) tensors."""
    from skimage.metrics import structural_similarity as ssim

    a = tensor_a.squeeze().cpu().numpy()
    b = tensor_b.squeeze().cpu().numpy()
    a = ((a + 1.0) / 2.0 * 255).clip(0, 255).astype(np.uint8)
    b = ((b + 1.0) / 2.0 * 255).clip(0, 255).astype(np.uint8)
    score, _ = ssim(a, b, full=True, data_range=255)
    return float(score)


def compute_psnr(tensor_a: torch.Tensor, tensor_b: torch.Tensor) -> float:
    """Compute Peak Signal-to-Noise Ratio between two (1,1,H,W) tensors."""
    from skimage.metrics import peak_signal_noise_ratio as psnr

    a = tensor_a.squeeze().cpu().numpy()
    b = tensor_b.squeeze().cpu().numpy()
    a = ((a + 1.0) / 2.0 * 255).clip(0, 255).astype(np.uint8)
    b = ((b + 1.0) / 2.0 * 255).clip(0, 255).astype(np.uint8)
    return float(psnr(a, b, data_range=255))
