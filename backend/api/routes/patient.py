from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from backend.api.schemas.patient_schema import PatientCreateIn, PatientOut, PatientUpdateIn
from backend.knowledge_graph import patient_store
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _compute_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _row_to_patient_out(row: dict) -> PatientOut:
    dob = date.fromisoformat(row["dob"]) if isinstance(row["dob"], str) else row["dob"]
    return PatientOut(
        patient_id=row["patient_id"],
        name=row["name"],
        age=_compute_age(dob),
        gender=row["gender"],
        dob=dob,
        created_at=datetime.fromisoformat(row["created_at"]) if isinstance(row["created_at"], str) else row["created_at"],
        notes=row.get("notes") or None,
    )


@router.post("", response_model=PatientOut, status_code=201)
async def create_patient(body: PatientCreateIn) -> PatientOut:
    """Create a new patient record."""
    try:
        row = patient_store.create_patient(
            name=body.name,
            dob=body.dob,
            gender=body.gender,
            notes=body.notes or "",
        )
        return _row_to_patient_out(row)
    except Exception as e:
        logger.error(f"create_patient failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[PatientOut])
async def list_patients() -> list[PatientOut]:
    """Return all patients."""
    try:
        rows = patient_store.list_patients()
        return [_row_to_patient_out(r) for r in rows]
    except Exception as e:
        logger.error(f"list_patients failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(patient_id: str) -> PatientOut:
    """Get a single patient by ID."""
    try:
        row = patient_store.get_patient(patient_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        return _row_to_patient_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_patient failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{patient_id}", response_model=PatientOut)
async def update_patient(patient_id: str, body: PatientUpdateIn) -> PatientOut:
    """Update patient name or notes."""
    try:
        updates = body.model_dump(exclude_none=True)
        ok = patient_store.update_patient(patient_id, updates)
        if not ok:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        row = patient_store.get_patient(patient_id)
        return _row_to_patient_out(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_patient failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
