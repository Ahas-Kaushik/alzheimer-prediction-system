from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.api.schemas.patient_schema import ClinicalFeaturesIn

AlzheimerStage = Literal["Normal", "MCI", "AD"]


class PredictionRunIn(BaseModel):
    patient_id: str
    visit_id: Optional[str] = None
    scan_id: Optional[str] = None
    # Free-form dict from the hybrid clinical form — only filled fields are present.
    # Field names follow the frontend form's naming (mapped in agent4_orchestrator).
    clinical_features: Optional[dict] = None
    cognitive_session_id: Optional[str] = None
    skip_cognitive_test: bool = False


class PredictionOut(BaseModel):
    pred_id: str
    patient_id: str
    visit_id: str
    stage: AlzheimerStage
    confidence: float = Field(..., ge=0.0, le=1.0)
    contributing_factors: list[str]
    run_date: datetime
    mri_path: Optional[str] = None
    pet_path: Optional[str] = None
    gradcam_path: Optional[str] = None
    cognitive_index: Optional[float] = None
    ssim_score: Optional[float] = None
    probabilities: Optional[dict] = None

    model_config = {"from_attributes": True}


class PredictionHistoryOut(BaseModel):
    patient_id: str
    predictions: list[PredictionOut]


class BrainRegion(BaseModel):
    name: str
    severity: float = Field(..., ge=0.0, le=1.0)
    status: AlzheimerStage


class LongitudinalPoint(BaseModel):
    visit_date: str
    stage: AlzheimerStage
    cognitive_index: Optional[float] = None
    hippocampal_volume_norm: Optional[float] = None


class DigitalTwinOut(BaseModel):
    patient_id: str
    generated_at: str
    current_stage: AlzheimerStage
    current_confidence: float
    regions: list[BrainRegion]
    longitudinal: list[LongitudinalPoint]
    neuron_connectivity: float = Field(..., ge=0.0, le=1.0)
    delta_from_last: Literal["improved", "stable", "declined"]
