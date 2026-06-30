"""PatchGAN 70x70 discriminator for Pix2Pix MRI→PET synthesis.

Classifies overlapping 70x70 patches as real/fake to encourage local texture realism.
Architecture follows Section 7.3 of PROJECT_KNOWLEDGE.md.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class PatchGANDiscriminator(nn.Module):
    """70x70 PatchGAN discriminator.

    Input:  concat(MRI, PET_or_synthetic) → (B, 2, 256, 256)
    Output: patch prediction map (B, 1, H', W') where each value = real/fake prob
    """

    def __init__(self, in_channels: int = 2):
        super().__init__()

        def conv_block(in_c: int, out_c: int, stride: int, norm: bool = True) -> nn.Sequential:
            layers: list[nn.Module] = [
                nn.Conv2d(in_c, out_c, kernel_size=4, stride=stride, padding=1, bias=not norm)
            ]
            if norm:
                layers.append(nn.InstanceNorm2d(out_c))
            layers.append(nn.LeakyReLU(0.2, inplace=True))
            return nn.Sequential(*layers)

        self.model = nn.Sequential(
            conv_block(in_channels, 64, stride=2, norm=False),   # (B, 64, 128, 128)
            conv_block(64, 128, stride=2),                        # (B, 128, 64, 64)
            conv_block(128, 256, stride=2),                       # (B, 256, 32, 32)
            conv_block(256, 512, stride=1),                       # (B, 512, 31, 31)
            nn.Conv2d(512, 1, kernel_size=4, stride=1, padding=1),# (B, 1, 30, 30)
        )

    def forward(self, mri: torch.Tensor, pet: torch.Tensor) -> torch.Tensor:
        x = torch.cat([mri, pet], dim=1)
        return self.model(x)
