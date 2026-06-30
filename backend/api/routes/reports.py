from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend.config import settings
from backend.knowledge_graph import patient_store
from backend.knowledge_graph.medication_mapper import get_medications, get_evidence_sources
from backend.models.ocr.ocr_engine import extract_text
from backend.models.ocr.report_parser import parse_report
from backend.models.report_generator import generate_pdf
from backend.utils.logger import get_logger
from backend.utils.validators import validate_report_file

router = APIRouter()
logger = get_logger(__name__)


class OCRPreviewOut(BaseModel):
    extracted_fields: dict
    raw_text_preview: str


class ReportConfirmIn(BaseModel):
    patient_id: str
    visit_id: str
    file_path: str
    source_type: str
    confirmed_fields: dict


@router.post("/upload", response_model=OCRPreviewOut)
async def upload_report(
    patient_id: str = Form(...),
    source_type: str = Form("general"),
    file: UploadFile = File(...),
) -> OCRPreviewOut:
    """Upload a clinical report image/PDF → OCR → return extracted fields for review."""
    try:
        validate_report_file(file.filename or "report.png")

        patient_dir = settings.upload_path / patient_id
        patient_dir.mkdir(parents=True, exist_ok=True)

        dest = patient_dir / f"report_{file.filename}"
        content = await file.read()
        dest.write_bytes(content)

        raw_text = extract_text(dest)
        fields = parse_report(raw_text)

        preview = raw_text[:500] + ("..." if len(raw_text) > 500 else "")
        return OCRPreviewOut(extracted_fields=fields, raw_text_preview=preview)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"report upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm")
async def confirm_report(body: ReportConfirmIn) -> dict:
    """Confirm and persist the (possibly edited) OCR-extracted fields."""
    try:
        row = patient_store.save_report(
            patient_id=body.patient_id,
            visit_id=body.visit_id,
            file_path=body.file_path,
            source_type=body.source_type,
            extracted_fields=body.confirmed_fields,
        )
        return {"report_id": row["report_id"], "message": "Report saved"}
    except Exception as e:
        logger.error(f"confirm_report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/medical/{patient_id}")
async def download_medical_report(patient_id: str) -> Response:
    """Generate and download a full medical PDF report for a patient.

    Gathers latest prediction, digital twin, and clinical data, then
    produces a downloadable PDF with medications from the knowledge graph.
    """
    try:
        patient = patient_store.get_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        latest_pred = patient_store.get_latest_prediction(patient_id)
        if not latest_pred:
            raise HTTPException(status_code=404, detail="No prediction found; run the pipeline first")

        twin_data = patient_store.get_digital_twin(patient_id)

        # Gather clinical features from last saved report (if any)
        import json as _json
        reports = patient_store.get_reports(patient_id)
        clinical = {}
        if reports:
            raw = reports[-1].get("extracted_fields_json", "") or reports[-1].get("extracted_fields", "")
            if isinstance(raw, dict):
                clinical = raw
            elif raw:
                try:
                    clinical = _json.loads(raw)
                except Exception:
                    clinical = {}

        stage = latest_pred.get("stage", "Unknown")
        meds = get_medications(
            stage=stage,
            age=_safe_float(clinical.get("age") or patient.get("age")),
            mmse=_safe_float(clinical.get("mmse_score")),
            apoe4=_safe_bool(clinical.get("apoe4_status")),
            cholesterol=_safe_float(clinical.get("cholesterol")),
            hdl=_safe_float(clinical.get("hdl")),
            ldl=_safe_float(clinical.get("ldl")),
            glucose=_safe_float(clinical.get("glucose")),
            hemoglobin=_safe_float(clinical.get("hemoglobin")),
            vit_b12=_safe_float(clinical.get("vit_b12")),
            hypertension=_safe_bool(clinical.get("hypertension")),
            diabetes=_safe_bool(clinical.get("diabetes")),
            depression=_safe_bool(clinical.get("depression")),
        )

        patient_dir = settings.upload_path / patient_id

        # Pre-rendered twin image
        twin_img_path: str | None = None
        twin_candidate = patient_dir / "twin_snapshot.png"
        if twin_candidate.is_file():
            twin_img_path = str(twin_candidate)

        from pathlib import Path as _Path

        def _resolve_path(raw: str | None) -> str | None:
            if not raw:
                return None
            p = _Path(raw)
            if p.is_file():
                return str(p)
            alt = _Path(settings.upload_path).parent.parent / p
            return str(alt) if alt.is_file() else None

        pet_img_path = _resolve_path(latest_pred.get("pet_path", ""))
        gradcam_img_path = _resolve_path(latest_pred.get("gradcam_path", ""))

        pdf_bytes = generate_pdf(
            patient=patient,
            prediction=latest_pred,
            twin_data=twin_data,
            medications=meds,
            twin_image_path=twin_img_path,
            pet_image_path=pet_img_path,
            gradcam_image_path=gradcam_img_path,
        )

        safe_name = patient.get("name", "patient").replace(" ", "_")
        filename = f"alzheimer_report_{safe_name}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"download_medical_report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/medications/{patient_id}")
async def get_medications_json(patient_id: str) -> list[dict]:
    """Return recommended medications as a JSON list (used to render on PatientProfile)."""
    import json as _json
    try:
        patient = patient_store.get_patient(patient_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        latest_pred = patient_store.get_latest_prediction(patient_id)
        if not latest_pred:
            return []

        reports = patient_store.get_reports(patient_id)
        clinical: dict = {}
        if reports:
            raw = reports[-1].get("extracted_fields_json", "") or reports[-1].get("extracted_fields", "")
            if isinstance(raw, dict):
                clinical = raw
            elif raw:
                try:
                    clinical = _json.loads(raw)
                except Exception:
                    clinical = {}

        stage = latest_pred.get("stage", "Normal")
        meds = get_medications(
            stage=stage,
            age=_safe_float(clinical.get("age") or patient.get("age")),
            mmse=_safe_float(clinical.get("mmse_score")),
            apoe4=_safe_bool(clinical.get("apoe4_status")),
            cholesterol=_safe_float(clinical.get("cholesterol")),
            hdl=_safe_float(clinical.get("hdl")),
            ldl=_safe_float(clinical.get("ldl")),
            glucose=_safe_float(clinical.get("glucose")),
            hemoglobin=_safe_float(clinical.get("hemoglobin")),
            vit_b12=_safe_float(clinical.get("vit_b12")),
            hypertension=_safe_bool(clinical.get("hypertension")),
            diabetes=_safe_bool(clinical.get("diabetes")),
            depression=_safe_bool(clinical.get("depression")),
        )
        return meds
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_medications_json failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evidence-sources")
async def get_clinical_evidence_sources() -> list[dict]:
    """Return the clinical guidelines and research sources backing the medication knowledge graph."""
    return get_evidence_sources()


@router.get("/{patient_id}")
async def list_reports(patient_id: str) -> list[dict]:
    """List all uploaded reports for a patient."""
    try:
        return patient_store.get_reports(patient_id)
    except Exception as e:
        logger.error(f"list_reports failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _safe_float(val) -> float | None:
    try:
        return float(val) if val not in (None, "", "null") else None
    except (ValueError, TypeError):
        return None


def _safe_bool(val) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "yes", "1", "positive")
