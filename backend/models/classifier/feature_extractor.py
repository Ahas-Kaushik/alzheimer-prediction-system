"""CNN feature extractor using pretrained ResNet-18 for MRI and synthetic PET images.

Extracts a 512-dimensional feature vector from each image tensor.
Architecture matches Section 6 (Agent 1) of PROJECT_KNOWLEDGE.md.
"""
from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn

_resnet_model: Optional[nn.Module] = None


def _get_resnet() -> nn.Module:
    """Lazy-load ResNet-18 for 512-d feature extraction.

    Preference order:
    1. Fine-tuned OASIS weights at resnet_extractor_checkpoint (best for Alzheimer's)
    2. ImageNet pretrained weights (fallback)
    """
    global _resnet_model
    if _resnet_model is not None:
        return _resnet_model

    from torchvision import models
    resnet = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)

    # Replace first conv to accept 1-channel grayscale (MRI/PET are grayscale)
    original_conv = resnet.conv1
    resnet.conv1 = nn.Conv2d(
        1, 64,
        kernel_size=original_conv.kernel_size,
        stride=original_conv.stride,
        padding=original_conv.padding,
        bias=False,
    )
    with torch.no_grad():
        resnet.conv1.weight.copy_(original_conv.weight.mean(dim=1, keepdim=True))

    resnet.fc = nn.Identity()

    # Load fine-tuned OASIS weights if available (overrides ImageNet init)
    try:
        from backend.config import settings
        ckpt = settings.resnet_extractor_checkpoint
        if ckpt.exists():
            state = torch.load(str(ckpt), map_location="cpu", weights_only=True)
            resnet.load_state_dict(state, strict=False)
    except Exception:
        pass  # silently fall back to ImageNet weights

    _resnet_model = resnet.eval()
    return _resnet_model


@torch.no_grad()
def extract_image_features(tensor: torch.Tensor) -> torch.Tensor:
    """Extract a 512-d feature vector from a (1, 1, 256, 256) image tensor.

    Args:
        tensor: Grayscale image in [-1, 1], shape (1, 1, H, W).

    Returns:
        Feature vector, shape (512,).
    """
    model = _get_resnet()
    device = next(model.parameters()).device
    tensor = tensor.to(device)
    features = model(tensor)          # (1, 512)
    return features.squeeze(0).cpu() # (512,)
