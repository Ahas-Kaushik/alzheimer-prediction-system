"""CSV-based dev fallback replacing Neo4j when USE_CSV_FALLBACK=True.

Each "table" is a CSV file under data/csv_db/. Relationships are encoded
as foreign-key columns (e.g. visit_id in the scans CSV).
"""
from __future__ import annotations

import csv
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_BASE = settings.csv_dir_path

_TABLES = {
    "patients": ["patient_id", "name", "dob", "gender", "created_at", "notes"],
    "visits": ["visit_id", "patient_id", "visit_date", "notes"],
    "mri_scans": ["scan_id", "visit_id", "patient_id", "file_path", "upload_date", "slice_used"],
    "synthetic_pets": ["pet_id", "scan_id", "patient_id", "file_path", "generated_at", "ssim_score", "psnr_score"],
    "clinical_features": [
        "feature_id", "visit_id", "patient_id",
        "age", "gender", "education_years",
        "mmse_score", "moca_score", "cdr_score",
        "apoe4_status",
        "amyloid_beta_42", "tau_protein", "p_tau_181",
        "hemoglobin", "glucose_fasting", "cholesterol_total",
        "hdl", "ldl", "triglycerides", "vitamin_b12", "thyroid_tsh",
        "smoking_history", "diabetes", "hypertension",
        "depression_history", "family_history_ad",
        "hippocampal_volume", "cortical_thickness", "wmh_volume",
    ],
    "cognitive_tests": [
        "test_id", "visit_id", "patient_id", "run_date",
        "reaction_time_avg_ms", "reaction_time_std_ms",
        "identification_accuracy", "gaze_stability_score",
        "saccade_count", "correct_count", "total_stimuli", "cognitive_index",
    ],
    "predictions": [
        "pred_id", "visit_id", "patient_id", "stage", "confidence",
        "contributing_factors", "run_date", "mri_path", "pet_path",
        "gradcam_path", "cognitive_index", "ssim_score", "probabilities",
    ],
    "digital_twins": [
        "twin_id", "visit_id", "patient_id", "generated_at",
        "neuron_connectivity", "delta_from_last", "regions_json",
    ],
    "reports": [
        "report_id", "visit_id", "patient_id", "file_path",
        "upload_date", "source_type", "extracted_fields_json",
    ],
}


def _csv_path(table: str) -> Path:
    return _BASE / f"{table}.csv"


def _init_tables() -> None:
    _BASE.mkdir(parents=True, exist_ok=True)
    for table, cols in _TABLES.items():
        p = _csv_path(table)
        if not p.exists():
            with p.open("w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=cols).writeheader()


def _read_table(table: str) -> list[dict[str, str]]:
    p = _csv_path(table)
    if not p.exists():
        _init_tables()
    with p.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _ensure_header(table: str) -> None:
    """Upgrade an existing CSV whose header is missing newly-added columns.

    Rewrites the file with the full current column set (old rows get empty
    values for new columns) so appends never misalign.
    """
    p = _csv_path(table)
    cols = _TABLES[table]
    if not p.exists():
        _init_tables()
        return
    with p.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing = reader.fieldnames or []
        rows = list(reader)
    if existing == cols:
        return
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in cols})


def _append_row(table: str, row: dict[str, Any]) -> None:
    _ensure_header(table)
    p = _csv_path(table)
    cols = _TABLES[table]
    # Ensure all columns present
    full_row = {c: row.get(c, "") for c in cols}
    with p.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writerow(full_row)


def _update_row(table: str, id_field: str, id_value: str, updates: dict[str, Any]) -> bool:
    rows = _read_table(table)
    cols = _TABLES[table]
    found = False
    for row in rows:
        if row[id_field] == id_value:
            row.update({k: str(v) for k, v in updates.items()})
            found = True
    if found:
        p = _csv_path(table)
        with p.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)
    return found


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ────────────────────────────────────────────────────────────────

def create_patient(name: str, dob: date, gender: str, notes: str = "") -> dict:
    _init_tables()
    patient_id = f"PAT-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "patient_id": patient_id,
        "name": name,
        "dob": str(dob),
        "gender": gender,
        "created_at": _now(),
        "notes": notes,
    }
    _append_row("patients", row)
    logger.info(f"CSV: created patient {patient_id}")
    return row


def get_patient(patient_id: str) -> Optional[dict]:
    rows = _read_table("patients")
    for r in rows:
        if r["patient_id"] == patient_id:
            return r
    return None


def list_patients() -> list[dict]:
    return _read_table("patients")


def update_patient(patient_id: str, updates: dict) -> bool:
    return _update_row("patients", "patient_id", patient_id, updates)


def create_visit(patient_id: str, notes: str = "") -> dict:
    _init_tables()
    visit_id = f"VIS-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "visit_date": _now(),
        "notes": notes,
    }
    _append_row("visits", row)
    return row


def get_visits(patient_id: str) -> list[dict]:
    return [r for r in _read_table("visits") if r["patient_id"] == patient_id]


def save_mri_scan(patient_id: str, visit_id: str, file_path: str, slice_used: Optional[int] = None) -> dict:
    _init_tables()
    scan_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "scan_id": scan_id,
        "visit_id": visit_id,
        "patient_id": patient_id,
        "file_path": file_path,
        "upload_date": _now(),
        "slice_used": str(slice_used) if slice_used is not None else "",
    }
    _append_row("mri_scans", row)
    return row


def get_latest_scan(patient_id: str) -> Optional[dict]:
    scans = [r for r in _read_table("mri_scans") if r["patient_id"] == patient_id]
    if not scans:
        return None
    return sorted(scans, key=lambda r: r["upload_date"])[-1]


def get_scan_by_id(scan_id: str, patient_id: str) -> Optional[dict]:
    for r in _read_table("mri_scans"):
        if r["scan_id"] == scan_id and r["patient_id"] == patient_id:
            return r
    return None


def get_all_scans(patient_id: str) -> list[dict]:
    scans = [r for r in _read_table("mri_scans") if r["patient_id"] == patient_id]
    return sorted(scans, key=lambda r: r["upload_date"])


def delete_mri_scan(scan_id: str, patient_id: str) -> Optional[str]:
    """Remove the scan record from CSV. Returns the file_path so the caller can delete the file."""
    rows = _read_table("mri_scans")
    cols = _TABLES["mri_scans"]
    target = None
    new_rows = []
    for r in rows:
        if r["scan_id"] == scan_id and r["patient_id"] == patient_id:
            target = r
        else:
            new_rows.append(r)
    if target is None:
        return None
    p = _csv_path("mri_scans")
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(new_rows)
    return target.get("file_path")


def save_synthetic_pet(patient_id: str, scan_id: str, file_path: str,
                       ssim_score: Optional[float] = None,
                       psnr_score: Optional[float] = None) -> dict:
    _init_tables()
    pet_id = f"PET-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "pet_id": pet_id,
        "scan_id": scan_id,
        "patient_id": patient_id,
        "file_path": file_path,
        "generated_at": _now(),
        "ssim_score": str(ssim_score) if ssim_score is not None else "",
        "psnr_score": str(psnr_score) if psnr_score is not None else "",
    }
    _append_row("synthetic_pets", row)
    return row


def save_clinical_features(patient_id: str, visit_id: str, features: dict) -> dict:
    _init_tables()
    feature_id = f"FTR-{uuid.uuid4().hex[:8].upper()}"
    row = {"feature_id": feature_id, "visit_id": visit_id, "patient_id": patient_id}
    row.update({k: str(v) if v is not None else "" for k, v in features.items()})
    _append_row("clinical_features", row)
    return row


def save_cognitive_test(patient_id: str, visit_id: str, scores: dict) -> dict:
    _init_tables()
    test_id = f"COG-{uuid.uuid4().hex[:8].upper()}"
    row = {"test_id": test_id, "visit_id": visit_id, "patient_id": patient_id, "run_date": _now()}
    row.update({k: str(v) for k, v in scores.items()})
    _append_row("cognitive_tests", row)
    return row


def get_cognitive_tests(patient_id: str) -> list[dict]:
    return [r for r in _read_table("cognitive_tests") if r["patient_id"] == patient_id]


def save_prediction(patient_id: str, visit_id: str, prediction: dict) -> dict:
    _init_tables()
    pred_id = f"PRD-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "pred_id": pred_id,
        "visit_id": visit_id,
        "patient_id": patient_id,
        "run_date": _now(),
    }
    row.update({k: str(v) for k, v in prediction.items()})
    _append_row("predictions", row)
    return row


def get_predictions(patient_id: str) -> list[dict]:
    rows = [r for r in _read_table("predictions") if r["patient_id"] == patient_id]
    return sorted(rows, key=lambda r: r["run_date"])


def get_latest_prediction(patient_id: str) -> Optional[dict]:
    preds = get_predictions(patient_id)
    return preds[-1] if preds else None


def save_digital_twin(patient_id: str, visit_id: str, twin_data: dict) -> dict:
    _init_tables()
    twin_id = f"TWN-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "twin_id": twin_id,
        "visit_id": visit_id,
        "patient_id": patient_id,
        "generated_at": _now(),
        "neuron_connectivity": str(twin_data.get("neuron_connectivity", 1.0)),
        "delta_from_last": twin_data.get("delta_from_last", "stable"),
        "regions_json": str(twin_data.get("regions", [])),
    }
    _append_row("digital_twins", row)
    return row


def get_digital_twin(patient_id: str) -> Optional[dict]:
    rows = [r for r in _read_table("digital_twins") if r["patient_id"] == patient_id]
    if not rows:
        return None
    return sorted(rows, key=lambda r: r["generated_at"])[-1]


def save_report(patient_id: str, visit_id: str, file_path: str,
                source_type: str, extracted_fields: dict) -> dict:
    _init_tables()
    import json
    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "report_id": report_id,
        "visit_id": visit_id,
        "patient_id": patient_id,
        "file_path": file_path,
        "upload_date": _now(),
        "source_type": source_type,
        "extracted_fields_json": json.dumps(extracted_fields),
    }
    _append_row("reports", row)
    return row


def get_reports(patient_id: str) -> list[dict]:
    return [r for r in _read_table("reports") if r["patient_id"] == patient_id]
