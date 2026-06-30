from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ClinicalFeaturesIn(BaseModel):
    """All clinical features that can be submitted for a patient visit."""

    age: int = Field(..., ge=0, le=120)
    gender: Literal["Male", "Female", "Other"]
    education_years: Optional[int] = Field(None, ge=0, le=30)

    mmse_score: Optional[float] = Field(None, ge=0, le=30)
    moca_score: Optional[float] = Field(None, ge=0, le=30)
    cdr_score: Optional[float] = None

    apoe4_status: Optional[Literal["Positive", "Negative", "Unknown"]] = "Unknown"

    amyloid_beta_42: Optional[float] = None
    tau_protein: Optional[float] = None
    p_tau_181: Optional[float] = None

    hemoglobin: Optional[float] = None
    glucose_fasting: Optional[float] = None
    cholesterol_total: Optional[float] = None
    hdl: Optional[float] = None
    ldl: Optional[float] = None
    triglycerides: Optional[float] = None
    vitamin_b12: Optional[float] = None
    thyroid_tsh: Optional[float] = None

    smoking_history: bool = False
    diabetes: bool = False
    hypertension: bool = False
    depression_history: bool = False
    family_history_ad: bool = False

    hippocampal_volume: Optional[float] = None
    cortical_thickness: Optional[float] = None
    wmh_volume: Optional[float] = None

    @field_validator("cdr_score")
    @classmethod
    def validate_cdr(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v not in {0, 0.5, 1, 2, 3}:
            raise ValueError("CDR score must be one of 0, 0.5, 1, 2, 3")
        return v


class PatientCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    dob: date
    gender: Literal["Male", "Female", "Other"]
    notes: Optional[str] = None


class PatientUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    notes: Optional[str] = None


class PatientOut(BaseModel):
    patient_id: str
    name: str
    age: int
    gender: str
    dob: date
    created_at: datetime
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
