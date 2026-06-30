"""Grad-CAM visualization for the ResNet-18 MRI feature extractor.

Highlights which spatial brain regions most influenced the Alzheimer's
stage prediction. Uses layer4 of ResNet-18 as the target layer.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image


def compute_gradcam(
    mri_tensor: torch.Tensor,
    resnet: nn.Module,
    mlp: nn.Module,
    predicted_class_idx: int,
    fused_dim: int = 1058,
) -> np.ndarray:
    """Compute Grad-CAM heatmap for the MRI with respect to the predicted stage.

    The MLP is fed a zero-padded vector (only MRI features filled in) so
    gradients only flow through the MRI branch — matching training conditions
    where PET features were zeros for the OASIS dataset.

    Args:
        mri_tensor: (1, 1, 256, 256) MRI in [-1, 1].
        resnet: ResNet-18 backbone (fc replaced with Identity).
        mlp: AlzheimerMLP classifier.
        predicted_class_idx: 0=Normal, 1=MCI, 2=AD.
        fused_dim: Total fused vector dimension fed to MLP.

    Returns:
        Normalized heatmap as (256, 256) float32 array in [0, 1].
    """
    activations: list = [None]
    gradients: list = [None]

    target_layer = resnet.layer4[-1]

    def _fwd_hook(m, inp, out):
        activations[0] = out.detach()

    def _bwd_hook(m, grad_in, grad_out):
        gradients[0] = grad_out[0]

    h_fwd = target_layer.register_forward_hook(_fwd_hook)
    h_bwd = target_layer.register_full_backward_hook(_bwd_hook)

    try:
        device = next(resnet.parameters()).device
        x = mri_tensor.to(device)

        with torch.enable_grad():
            resnet.zero_grad()
            mlp.zero_grad()

            mri_feats = resnet(x)                                    # (1, 512)
            pad = torch.zeros(1, fused_dim - mri_feats.shape[1], device=device)
            fused = torch.cat([mri_feats, pad], dim=1)               # (1, fused_dim)

            logits = mlp(fused)                                      # (1, 3)
            logits[0, predicted_class_idx].backward()

        act = activations[0]   # (1, C, H', W') — e.g. (1, 512, 8, 8)
        grad = gradients[0]    # same shape

        weights = grad.mean(dim=[2, 3], keepdim=True)                # (1, C, 1, 1)
        cam = F.relu((weights * act).sum(dim=1, keepdim=True))       # (1, 1, H', W')
        cam = F.interpolate(cam, size=(256, 256), mode="bilinear", align_corners=False)

        cam_np = cam.squeeze().detach().cpu().numpy()                # (256, 256)
        lo, hi = cam_np.min(), cam_np.max()
        cam_np = (cam_np - lo) / (hi - lo) if hi > lo else np.zeros_like(cam_np)

    finally:
        h_fwd.remove()
        h_bwd.remove()

    return cam_np


def save_gradcam_overlay(
    mri_tensor: torch.Tensor,
    cam: np.ndarray,
    out_path: Path | str,
    alpha: float = 0.5,
) -> None:
    """Blend Grad-CAM heatmap with the MRI and save as RGB PNG.

    Hot colormap: black → red → yellow → white (matches clinical PET scale).
    """
    mri_np = mri_tensor.squeeze().cpu().numpy()
    mri_u8 = ((mri_np + 1.0) / 2.0 * 255).clip(0, 255).astype(np.uint8)
    mri_rgb = np.stack([mri_u8] * 3, axis=-1)                       # (H, W, 3)

    h, w = cam.shape
    r = np.zeros((h, w), np.float32)
    g = np.zeros((h, w), np.float32)
    b_ch = np.zeros((h, w), np.float32)

    m1 = cam < 0.33
    r[m1] = cam[m1] / 0.33

    m2 = (cam >= 0.33) & (cam < 0.66)
    r[m2] = 1.0
    g[m2] = (cam[m2] - 0.33) / 0.33

    m3 = cam >= 0.66
    r[m3] = 1.0
    g[m3] = 1.0
    b_ch[m3] = (cam[m3] - 0.66) / 0.34

    cam_rgb = np.stack([
        (r * 255).clip(0, 255).astype(np.uint8),
        (g * 255).clip(0, 255).astype(np.uint8),
        (b_ch * 255).clip(0, 255).astype(np.uint8),
    ], axis=-1)

    overlay = (alpha * cam_rgb + (1.0 - alpha) * mri_rgb).clip(0, 255).astype(np.uint8)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(overlay, mode="RGB").save(str(out_path))
