"""GAN training script — Pix2Pix MRI→PET synthesis on ADNI dataset.

Optimized for RTX 3070 Ti (8 GB VRAM) with AMP + gradient accumulation.

=== QUICK START (after running adni_preprocess.py) ===
  python -m backend.models.gan.train --cuda

=== FULL OPTIONS ===
  python -m backend.models.gan.train \\
      --data_dir data/processed \\
      --epochs 200 \\
      --batch_size 4 \\        # safe for 8GB with AMP; increase to 8 if no OOM
      --accum_steps 4 \\       # effective batch = batch_size * accum_steps = 16
      --cuda \\                 # enable CUDA (auto-detects if available)
      --amp \\                  # Automatic Mixed Precision (recommended for 3070 Ti)
      --save_dir data/checkpoints \\
      --save_every 10

=== EXPECTED TRAINING TIME ===
  ~1000 ADNI pairs: ~20 min/epoch on 3070 Ti with AMP
  200 epochs ≈ 67 hours total (run overnight; use tmux/screen)
  Usable results visible from epoch 30–50 (SSIM > 0.6)
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
import torchvision.transforms.functional as TF
from PIL import Image

from backend.models.gan.discriminator import PatchGANDiscriminator
from backend.models.gan.generator import LightweightUNetGenerator
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Synced augmentation (same random transform applied to MRI + PET pair)
# ---------------------------------------------------------------------------

class SyncedAugment:
    """Apply the same random spatial + photometric transforms to MRI/PET pair.

    Both images receive identical spatial transforms (flip, rotate) so their
    alignment is preserved.  Brightness jitter is MRI-only because PET pixel
    values represent metabolic activity that should not be artificially shifted.
    """

    def __init__(self, size: int = 256):
        self.size = size

    def __call__(self, mri_img: Image.Image, pet_img: Image.Image):
        mri_img = TF.resize(mri_img, (self.size, self.size))
        pet_img = TF.resize(pet_img, (self.size, self.size))

        if random.random() > 0.5:
            mri_img = TF.hflip(mri_img)
            pet_img = TF.hflip(pet_img)

        if random.random() > 0.3:
            mri_img = TF.vflip(mri_img)
            pet_img = TF.vflip(pet_img)

        angle = random.uniform(-12.0, 12.0)
        mri_img = TF.rotate(mri_img, angle, fill=0)
        pet_img = TF.rotate(pet_img, angle, fill=0)

        # Mild MRI brightness jitter only (±10%)
        mri_img = TF.adjust_brightness(mri_img, random.uniform(0.90, 1.10))

        mri_t = TF.normalize(TF.to_tensor(TF.to_grayscale(mri_img)), [0.5], [0.5])
        pet_t = TF.normalize(TF.to_tensor(TF.to_grayscale(pet_img)), [0.5], [0.5])
        return mri_t, pet_t


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class MRIPETPairDataset(Dataset):
    """Paired MRI/PET dataset.

    Modes:
    1. CSV (preferred): reads pairs from train.csv / val.csv
    2. Directory fallback: scans mri/ and pet/ subdirectories

    Pass augment=True for the training split to enable SyncedAugment.
    """

    def __init__(self, root: str | Path, size: int = 256, split: str = "train",
                 augment: bool = False):
        try:
            import pandas as pd
            use_pandas = True
        except ImportError:
            use_pandas = False

        root = Path(root)
        self.augment = augment
        self._aug = SyncedAugment(size) if augment else None
        self.transform = transforms.Compose([
            transforms.Resize((size, size)),
            transforms.Grayscale(),
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5]),
        ])

        csv_path = root / f"{split}.csv"
        if csv_path.exists() and use_pandas:
            import pandas as pd
            logger.info(f"Loading pairs from {csv_path}")
            df = pd.read_csv(csv_path)
            self.pairs = list(zip(df["mri_path"].tolist(), df["pet_path"].tolist()))
        else:
            logger.info(f"No {split}.csv — scanning mri/ directory")
            mri_dir = root / "mri"
            pet_dir = root / "pet"
            files = sorted(mri_dir.glob("*.png")) + sorted(mri_dir.glob("*.jpg"))
            self.pairs = [(str(f), str(pet_dir / f.name)) for f in files]

        aug_label = " + augment" if augment else ""
        logger.info(f"Dataset [{split}{aug_label}]: {len(self.pairs)} pairs")

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        mri_path, pet_path = self.pairs[idx]
        mri_img = Image.open(mri_path).convert("L")
        pet_img = Image.open(pet_path).convert("L")
        if self.augment and self._aug is not None:
            return self._aug(mri_img, pet_img)
        return self.transform(mri_img), self.transform(pet_img)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train(
    data_dir: str = "data/processed",
    epochs: int = 200,
    batch_size: int = 4,
    accum_steps: int = 4,     # gradient accumulation → effective bs = batch_size * accum_steps
    lr: float = 2e-4,
    lambda_l1: float = 100.0,
    save_dir: str = "data/checkpoints",
    save_every: int = 10,
    cuda: bool = True,
    amp: bool = True,         # Automatic Mixed Precision (strongly recommended for 3070 Ti)
    resume: bool = False,     # resume from latest checkpoint
    augment: bool = False,    # enable SyncedAugment on training split
    patience: int = 0,        # early stopping: stop after N epochs with no SSIM gain (0=off)
) -> None:
    # Device selection
    if cuda and torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        logger.info(f"GPU: {gpu_name} | VRAM: {vram_gb:.1f} GB")
        # RTX 3070 Ti optimisations
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    else:
        device = torch.device("cpu")
        amp = False  # AMP only makes sense on CUDA
        logger.info("Training on CPU — this will be very slow. Use --cuda flag.")

    logger.info(f"AMP: {amp} | batch_size: {batch_size} | accum_steps: {accum_steps} | "
                f"effective_batch: {batch_size * accum_steps} | augment: {augment} | patience: {patience}")

    # Datasets
    train_ds = MRIPETPairDataset(data_dir, split="train", augment=augment)
    val_ds = MRIPETPairDataset(data_dir, split="val", augment=False)

    if len(train_ds) == 0:
        logger.error(
            "No training pairs found! Run: python data/adni_preprocess.py first."
        )
        return

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=4 if device.type == "cuda" else 0,
        pin_memory=device.type == "cuda",
        persistent_workers=device.type == "cuda",
    )
    val_loader = DataLoader(
        val_ds, batch_size=1, shuffle=False,
        num_workers=0,
    )

    # Models
    G = LightweightUNetGenerator().to(device)
    D = PatchGANDiscriminator().to(device)

    # Optimizers
    opt_G = torch.optim.Adam(G.parameters(), lr=lr, betas=(0.5, 0.999))
    opt_D = torch.optim.Adam(D.parameters(), lr=lr, betas=(0.5, 0.999))

    # LR schedulers: linear decay after 50% of training
    def lr_lambda(epoch: int) -> float:
        decay_start = epochs // 2
        if epoch < decay_start:
            return 1.0
        return max(0.0, 1.0 - (epoch - decay_start) / decay_start)

    sched_G = torch.optim.lr_scheduler.LambdaLR(opt_G, lr_lambda)
    sched_D = torch.optim.lr_scheduler.LambdaLR(opt_D, lr_lambda)

    # Loss functions
    criterion_GAN = nn.BCEWithLogitsLoss()
    criterion_L1 = nn.L1Loss()

    # AMP scaler
    scaler_G = torch.amp.GradScaler("cuda", enabled=amp)
    scaler_D = torch.amp.GradScaler("cuda", enabled=amp)

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    start_epoch = 1
    best_ssim = 0.0

    # Resume from checkpoint
    if resume:
        ckpts = sorted(save_path.glob("gan_generator_epoch*.pth"))
        if ckpts:
            latest = ckpts[-1]
            epoch_num = int(latest.stem.split("epoch")[-1])
            G.load_state_dict(torch.load(str(latest), map_location=device, weights_only=True))
            d_ckpt = save_path / f"gan_discriminator_epoch{epoch_num}.pth"
            if d_ckpt.exists():
                D.load_state_dict(torch.load(str(d_ckpt), map_location=device, weights_only=True))
            start_epoch = epoch_num + 1
            logger.info(f"Resumed from epoch {epoch_num}")

    logger.info(f"Starting training: epochs {start_epoch}→{epochs}, "
                f"{len(train_ds)} train / {len(val_ds)} val pairs")

    no_improve_count = 0

    for epoch in range(start_epoch, epochs + 1):
        G.train()
        D.train()
        total_G = total_D = 0.0
        n_batches = 0

        opt_G.zero_grad()
        opt_D.zero_grad()

        for step, (mri, real_pet) in enumerate(train_loader):
            mri = mri.to(device, non_blocking=True)
            real_pet = real_pet.to(device, non_blocking=True)

            # ── Discriminator ────────────────────────────────────────────────
            with torch.amp.autocast("cuda", enabled=amp):
                fake_pet = G(mri)
                real_pred = D(mri, real_pet)
                fake_pred = D(mri, fake_pet.detach())
                real_label = torch.ones_like(real_pred)
                fake_label = torch.zeros_like(fake_pred)
                loss_D = (
                    criterion_GAN(real_pred, real_label) +
                    criterion_GAN(fake_pred, fake_label)
                ) * 0.5 / accum_steps

            scaler_D.scale(loss_D).backward()
            total_D += loss_D.item() * accum_steps

            # ── Generator ────────────────────────────────────────────────────
            with torch.amp.autocast("cuda", enabled=amp):
                fake_pred2 = D(mri, fake_pet)
                loss_GAN = criterion_GAN(fake_pred2, torch.ones_like(fake_pred2))
                loss_L1 = criterion_L1(fake_pet, real_pet) * lambda_l1
                loss_G = (loss_GAN + loss_L1) / accum_steps

            scaler_G.scale(loss_G).backward()
            total_G += loss_G.item() * accum_steps
            n_batches += 1

            # Apply gradients after accum_steps
            if (step + 1) % accum_steps == 0 or (step + 1) == len(train_loader):
                scaler_D.step(opt_D)
                scaler_D.update()
                opt_D.zero_grad()

                scaler_G.step(opt_G)
                scaler_G.update()
                opt_G.zero_grad()

        sched_G.step()
        sched_D.step()

        avg_G = total_G / n_batches if n_batches else 0
        avg_D = total_D / n_batches if n_batches else 0

        # Validation SSIM
        val_ssim = _compute_val_ssim(G, val_loader, device, amp)

        logger.info(
            f"Epoch [{epoch}/{epochs}] "
            f"G={avg_G:.4f} D={avg_D:.4f} "
            f"val_SSIM={val_ssim:.4f} "
            f"lr={sched_G.get_last_lr()[0]:.2e}"
        )

        # Save best / early stopping
        if val_ssim > best_ssim:
            best_ssim = val_ssim
            no_improve_count = 0
            torch.save(G.state_dict(), save_path / "gan_generator_best.pth")
            logger.info(f"  -> New best SSIM {best_ssim:.4f} — saved gan_generator_best.pth")
        else:
            no_improve_count += 1
            if patience > 0 and no_improve_count >= patience:
                logger.info(
                    f"  -> Early stopping at epoch {epoch} "
                    f"(no SSIM improvement for {patience} consecutive epochs)"
                )
                break

        if epoch % save_every == 0:
            torch.save(G.state_dict(), save_path / f"gan_generator_epoch{epoch}.pth")
            torch.save(D.state_dict(), save_path / f"gan_discriminator_epoch{epoch}.pth")
            logger.info(f"  -> Checkpoint saved at epoch {epoch}")

        # Free GPU cache periodically
        if device.type == "cuda":
            torch.cuda.empty_cache()

    # Final checkpoint (also copy best as the active inference checkpoint)
    torch.save(G.state_dict(), save_path / "gan_generator.pth")
    import shutil
    best = save_path / "gan_generator_best.pth"
    if best.exists():
        shutil.copy(str(best), str(save_path / "gan_generator.pth"))
        logger.info("Final checkpoint = best validation SSIM model")
    logger.info(f"Training complete. Best val SSIM: {best_ssim:.4f}")
    logger.info(f"Checkpoint: {save_path}/gan_generator.pth")


@torch.no_grad()
def _compute_val_ssim(G, val_loader, device, amp: bool) -> float:
    """Compute average SSIM on validation set."""
    try:
        from skimage.metrics import structural_similarity as ssim
        import numpy as np
    except ImportError:
        return 0.0

    G.eval()
    scores = []
    for mri, real_pet in val_loader:
        mri = mri.to(device)
        with torch.amp.autocast("cuda", enabled=amp):
            fake_pet = G(mri)

        def to_u8(t: torch.Tensor) -> "np.ndarray":
            return ((t.squeeze().cpu().float().numpy() + 1) / 2 * 255).clip(0, 255).astype("uint8")

        score, _ = ssim(to_u8(real_pet), to_u8(fake_pet), full=True, data_range=255)
        scores.append(float(score))

    G.train()
    return float(sum(scores) / len(scores)) if scores else 0.0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train Pix2Pix GAN for MRI→PET (optimised for RTX 3070 Ti 8 GB)"
    )
    parser.add_argument("--data_dir", default="data/processed",
                        help="Root dir with train.csv/val.csv from adni_preprocess.py")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=4,
                        help="Per-GPU batch size. 4 is safe for 8 GB VRAM with AMP")
    parser.add_argument("--accum_steps", type=int, default=4,
                        help="Gradient accumulation steps. Effective batch = batch_size * accum_steps")
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lambda_l1", type=float, default=100.0)
    parser.add_argument("--save_dir", default="data/checkpoints")
    parser.add_argument("--save_every", type=int, default=10)
    parser.add_argument("--cuda", action="store_true", default=True,
                        help="Use CUDA GPU (default: True)")
    parser.add_argument("--no-cuda", action="store_false", dest="cuda")
    parser.add_argument("--amp", action="store_true", default=True,
                        help="Automatic Mixed Precision — strongly recommended for 3070 Ti")
    parser.add_argument("--no-amp", action="store_false", dest="amp")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from latest epoch checkpoint in save_dir")
    parser.add_argument("--augment", action="store_true", default=False,
                        help="Enable SyncedAugment on training split (recommended for small datasets)")
    parser.add_argument("--patience", type=int, default=0,
                        help="Early stopping: stop after N epochs with no val SSIM improvement (0=off)")
    args = parser.parse_args()
    train(**vars(args))
