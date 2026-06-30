"""Fine-tune the generator from a pretrained junyanz/pytorch-CycleGAN-and-pix2pix checkpoint.

The pretrained checkpoint uses standard (non-depthwise-sep) Conv2d layers.
This script copies compatible weights by layer name where shapes match, then
continues training with our lightweight U-Net.

Run:
    python -m backend.models.gan.fine_tune \\
        --pretrained_ckpt /path/to/latest_net_G.pth \\
        --data_dir data/raw \\
        --epochs 100
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch

from backend.models.gan.generator import LightweightUNetGenerator
from backend.models.gan.train import train
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def load_pretrained_weights(
    generator: LightweightUNetGenerator,
    pretrained_ckpt: str | Path,
    strict: bool = False,
) -> LightweightUNetGenerator:
    """Copy compatible weights from a pretrained Pix2Pix checkpoint.

    Args:
        generator: Our lightweight U-Net instance.
        pretrained_ckpt: Path to the pretrained state_dict (.pth).
        strict: If False, skip layers with shape mismatches (expected since our
                encoder uses depthwise-sep conv with different shapes).
    """
    ckpt = Path(pretrained_ckpt)
    if not ckpt.exists():
        raise FileNotFoundError(f"Pretrained checkpoint not found: {ckpt}")

    pretrained_state = torch.load(str(ckpt), map_location="cpu")
    if "state_dict" in pretrained_state:
        pretrained_state = pretrained_state["state_dict"]

    our_state = generator.state_dict()
    matched, skipped = 0, 0

    for key, param in pretrained_state.items():
        clean_key = key.replace("module.", "")
        if clean_key in our_state and our_state[clean_key].shape == param.shape:
            our_state[clean_key] = param
            matched += 1
        else:
            skipped += 1

    generator.load_state_dict(our_state, strict=False)
    logger.info(f"Fine-tune init: {matched} weights matched, {skipped} skipped (shape mismatch)")
    return generator


def fine_tune(
    pretrained_ckpt: str,
    data_dir: str,
    epochs: int = 100,
    batch_size: int = 4,
    lr: float = 2e-4,
    lambda_l1: float = 100.0,
    save_dir: str = "data/checkpoints",
) -> None:
    # Pre-load weights, then hand off to the standard train loop
    G = LightweightUNetGenerator()
    load_pretrained_weights(G, pretrained_ckpt)

    tmp_ckpt = Path(save_dir) / "_finetune_init.pth"
    tmp_ckpt.parent.mkdir(parents=True, exist_ok=True)
    torch.save(G.state_dict(), str(tmp_ckpt))
    logger.info(f"Saved fine-tune init checkpoint to {tmp_ckpt}")

    train(
        data_dir=data_dir,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        lambda_l1=lambda_l1,
        save_dir=save_dir,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretrained_ckpt", required=True)
    parser.add_argument("--data_dir", default="data/raw")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lambda_l1", type=float, default=100.0)
    parser.add_argument("--save_dir", default="data/checkpoints")
    args = parser.parse_args()
    fine_tune(**vars(args))
