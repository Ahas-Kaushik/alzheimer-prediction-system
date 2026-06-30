"""Lightweight U-Net generator with Depthwise Separable Convolutions for MRI→PET synthesis.

Architecture follows Section 7.2 of PROJECT_KNOWLEDGE.md exactly.
Replaces standard Conv2d in the encoder with DSSConvBlock to reduce parameters ~8x.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class DSSConvBlock(nn.Module):
    """Depthwise Separable Conv block: depthwise → pointwise → InstanceNorm → LeakyReLU."""

    def __init__(self, in_ch: int, out_ch: int, stride: int = 1):
        super().__init__()
        self.dw = nn.Conv2d(in_ch, in_ch, 3, stride, 1, groups=in_ch, bias=False)
        self.pw = nn.Conv2d(in_ch, out_ch, 1, bias=False)
        self.bn = nn.InstanceNorm2d(out_ch)
        self.act = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(self.bn(self.pw(self.dw(x))))


class DecoderBlock(nn.Module):
    """Upsample + DSS Conv + skip connection concatenation."""

    def __init__(self, in_ch: int, skip_ch: int, out_ch: int, dropout: bool = False):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_ch, out_ch, kernel_size=4, stride=2, padding=1, bias=False)
        self.norm = nn.InstanceNorm2d(out_ch)
        self.act = nn.ReLU(inplace=True)
        self.dss = DSSConvBlock(out_ch + skip_ch, out_ch)
        self.drop = nn.Dropout(0.5) if dropout else nn.Identity()

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.act(self.norm(self.up(x)))
        x = self.drop(x)
        x = torch.cat([x, skip], dim=1)
        return self.dss(x)


class LightweightUNetGenerator(nn.Module):
    """Pix2Pix generator: lightweight U-Net with depthwise separable conv encoder.

    Input:  (B, 1, 256, 256) — grayscale MRI in [-1, 1]
    Output: (B, 1, 256, 256) — synthetic PET in [-1, 1]
    """

    def __init__(self):
        super().__init__()

        # Encoder (downsampling) — DSSConv blocks
        self.enc1 = DSSConvBlock(1, 64, stride=2)    # → (B, 64, 128, 128)
        self.enc2 = DSSConvBlock(64, 128, stride=2)  # → (B, 128, 64, 64)
        self.enc3 = DSSConvBlock(128, 256, stride=2) # → (B, 256, 32, 32)
        self.enc4 = DSSConvBlock(256, 512, stride=2) # → (B, 512, 16, 16)
        self.enc5 = DSSConvBlock(512, 512, stride=2) # → (B, 512, 8, 8)

        # Bottleneck — standard conv (maintains full receptive field)
        self.bottleneck = nn.Sequential(
            nn.Conv2d(512, 512, 4, stride=2, padding=1, bias=False),  # → (B, 512, 4, 4)
            nn.ReLU(inplace=True),
        )

        # Decoder (upsampling + skip connections)
        # Dropout on first 3 decoder blocks for regularization (original Pix2Pix)
        self.dec1 = DecoderBlock(512, 512, 512, dropout=True)   # → (B, 512, 8, 8)
        self.dec2 = DecoderBlock(512, 512, 512, dropout=True)   # → (B, 512, 16, 16)
        self.dec3 = DecoderBlock(512, 256, 256, dropout=True)   # → (B, 256, 32, 32)
        self.dec4 = DecoderBlock(256, 128, 128)                  # → (B, 128, 64, 64)
        self.dec5 = DecoderBlock(128, 64, 64)                    # → (B, 64, 128, 128)

        # Final upsampling to output
        self.final = nn.Sequential(
            nn.ConvTranspose2d(64, 1, kernel_size=4, stride=2, padding=1),  # → (B, 1, 256, 256)
            nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encode
        e1 = self.enc1(x)
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)
        e5 = self.enc5(e4)

        # Bottleneck
        b = self.bottleneck(e5)

        # Decode with skip connections
        d1 = self.dec1(b, e5)
        d2 = self.dec2(d1, e4)
        d3 = self.dec3(d2, e3)
        d4 = self.dec4(d3, e2)
        d5 = self.dec5(d4, e1)

        return self.final(d5)
