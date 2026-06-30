from __future__ import annotations

from pathlib import Path

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".nii", ".gz", ".dcm"}
ALLOWED_REPORT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".tiff", ".tif"}
MAX_UPLOAD_SIZE_MB = 50


def validate_image_file(filename: str, content_length: int | None = None) -> None:
    """Raise ValueError if the file extension or size is not acceptable for MRI uploads."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{ext}'. Allowed: {ALLOWED_IMAGE_EXTENSIONS}"
        )
    if content_length is not None:
        _check_size(content_length)


def validate_report_file(filename: str, content_length: int | None = None) -> None:
    """Raise ValueError if the file is not a supported clinical report format."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_REPORT_EXTENSIONS:
        raise ValueError(
            f"Unsupported report format '{ext}'. Allowed: {ALLOWED_REPORT_EXTENSIONS}"
        )
    if content_length is not None:
        _check_size(content_length)


def validate_patient_age(age: int) -> None:
    if not (0 <= age <= 120):
        raise ValueError(f"Age must be between 0 and 120, got {age}")


def validate_mmse_score(score: float) -> None:
    if not (0 <= score <= 30):
        raise ValueError(f"MMSE score must be in [0, 30], got {score}")


def validate_moca_score(score: float) -> None:
    if not (0 <= score <= 30):
        raise ValueError(f"MoCA score must be in [0, 30], got {score}")


def validate_cdr_score(score: float) -> None:
    if score not in {0, 0.5, 1, 2, 3}:
        raise ValueError(f"CDR score must be one of {{0, 0.5, 1, 2, 3}}, got {score}")


def _check_size(content_length: int) -> None:
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if content_length > max_bytes:
        raise ValueError(
            f"File too large: {content_length / 1e6:.1f} MB exceeds limit of {MAX_UPLOAD_SIZE_MB} MB"
        )
