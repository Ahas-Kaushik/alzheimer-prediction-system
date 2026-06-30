from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScanUploadOut(BaseModel):
    scan_id: str
    patient_id: str
    file_path: str
    upload_date: datetime
    slice_used: Optional[int] = None
    message: str = "MRI scan uploaded successfully"


class SyntheticPETOut(BaseModel):
    pet_id: str
    scan_id: str
    patient_id: str
    file_path: str                          # physics-based PET (used in detection)
    heatmap_file_path: Optional[str] = None # GAN activity heatmap (visualization only)
    generated_at: datetime
    ssim_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    psnr_score: Optional[float] = None
    is_fallback: bool = True   # physics-based PET is always used for detection
    message: str = "Synthetic PET generated"


class ScanStatusOut(BaseModel):
    scan_id: str
    patient_id: str
    mri_path: str
    pet_path: Optional[str] = None
    pet_generated: bool = False
    ssim_score: Optional[float] = None
    psnr_score: Optional[float] = None
