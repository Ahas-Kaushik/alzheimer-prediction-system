"""Unified patient data store — routes to CSV fallback or Neo4j based on config."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

if settings.use_csv_fallback:
    from backend.knowledge_graph import csv_fallback as _backend
else:
    from backend.knowledge_graph import neo4j_client as _neo4j  # type: ignore


def create_patient(name: str, dob: date, gender: str, notes: str = "") -> dict:
    if settings.use_csv_fallback:
        return _backend.create_patient(name, dob, gender, notes)
    raise NotImplementedError("Neo4j patient creation not yet implemented")


def get_patient(patient_id: str) -> Optional[dict]:
    if settings.use_csv_fallback:
        return _backend.get_patient(patient_id)
    raise NotImplementedError


def list_patients() -> list[dict]:
    if settings.use_csv_fallback:
        return _backend.list_patients()
    raise NotImplementedError


def update_patient(patient_id: str, updates: dict) -> bool:
    if settings.use_csv_fallback:
        return _backend.update_patient(patient_id, updates)
    raise NotImplementedError


def create_visit(patient_id: str, notes: str = "") -> dict:
    if settings.use_csv_fallback:
        return _backend.create_visit(patient_id, notes)
    raise NotImplementedError


def get_visits(patient_id: str) -> list[dict]:
    if settings.use_csv_fallback:
        return _backend.get_visits(patient_id)
    raise NotImplementedError


def save_mri_scan(patient_id: str, visit_id: str, file_path: str,
                  slice_used: Optional[int] = None) -> dict:
    if settings.use_csv_fallback:
        return _backend.save_mri_scan(patient_id, visit_id, file_path, slice_used)
    raise NotImplementedError


def get_latest_scan(patient_id: str) -> Optional[dict]:
    if settings.use_csv_fallback:
        return _backend.get_latest_scan(patient_id)
    raise NotImplementedError


def get_scan_by_id(scan_id: str, patient_id: str) -> Optional[dict]:
    if settings.use_csv_fallback:
        return _backend.get_scan_by_id(scan_id, patient_id)
    raise NotImplementedError


def get_all_scans(patient_id: str) -> list[dict]:
    if settings.use_csv_fallback:
        return _backend.get_all_scans(patient_id)
    raise NotImplementedError


def delete_mri_scan(scan_id: str, patient_id: str) -> Optional[str]:
    """Delete scan record and return the file_path (or None if not found)."""
    if settings.use_csv_fallback:
        return _backend.delete_mri_scan(scan_id, patient_id)
    raise NotImplementedError


def save_synthetic_pet(patient_id: str, scan_id: str, file_path: str,
                       ssim_score: Optional[float] = None,
                       psnr_score: Optional[float] = None) -> dict:
    if settings.use_csv_fallback:
        return _backend.save_synthetic_pet(patient_id, scan_id, file_path, ssim_score, psnr_score)
    raise NotImplementedError


def save_clinical_features(patient_id: str, visit_id: str, features: dict) -> dict:
    if settings.use_csv_fallback:
        return _backend.save_clinical_features(patient_id, visit_id, features)
    raise NotImplementedError


def save_cognitive_test(patient_id: str, visit_id: str, scores: dict) -> dict:
    if settings.use_csv_fallback:
        return _backend.save_cognitive_test(patient_id, visit_id, scores)
    raise NotImplementedError


def get_cognitive_tests(patient_id: str) -> list[dict]:
    if settings.use_csv_fallback:
        return _backend.get_cognitive_tests(patient_id)
    raise NotImplementedError


def save_prediction(patient_id: str, visit_id: str, prediction: dict) -> dict:
    if settings.use_csv_fallback:
        return _backend.save_prediction(patient_id, visit_id, prediction)
    raise NotImplementedError


def get_predictions(patient_id: str) -> list[dict]:
    if settings.use_csv_fallback:
        return _backend.get_predictions(patient_id)
    raise NotImplementedError


def get_latest_prediction(patient_id: str) -> Optional[dict]:
    if settings.use_csv_fallback:
        return _backend.get_latest_prediction(patient_id)
    raise NotImplementedError


def save_digital_twin(patient_id: str, visit_id: str, twin_data: dict) -> dict:
    if settings.use_csv_fallback:
        return _backend.save_digital_twin(patient_id, visit_id, twin_data)
    raise NotImplementedError


def get_digital_twin(patient_id: str) -> Optional[dict]:
    if settings.use_csv_fallback:
        return _backend.get_digital_twin(patient_id)
    raise NotImplementedError


def save_report(patient_id: str, visit_id: str, file_path: str,
                source_type: str, extracted_fields: dict) -> dict:
    if settings.use_csv_fallback:
        return _backend.save_report(patient_id, visit_id, file_path, source_type, extracted_fields)
    raise NotImplementedError


def get_reports(patient_id: str) -> list[dict]:
    if settings.use_csv_fallback:
        return _backend.get_reports(patient_id)
    raise NotImplementedError
