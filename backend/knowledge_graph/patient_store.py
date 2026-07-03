"""Unified patient data store.

Routes every call to the active backend:

  * **Neo4j** knowledge graph (preferred) when ``GRAPH_BACKEND=neo4j`` and the
    server is reachable, or
  * the **CSV** dev store — used directly when ``GRAPH_BACKEND=csv`` /
    ``USE_CSV_FALLBACK=True``, or automatically when Neo4j is down and
    ``ALLOW_CSV_FALLBACK=True``.

The backend is chosen once per process and cached. All backends expose the
same function names, so this module just forwards the call.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from backend.config import settings
from backend.knowledge_graph import csv_fallback
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_backend_cache = None
_ACTIVE = "unknown"


def _select_backend():
    """Pick and cache the storage backend, with graceful fallback to CSV."""
    global _backend_cache, _ACTIVE
    if _backend_cache is not None:
        return _backend_cache

    # Explicit CSV selection (legacy flag or config).
    if settings.use_csv_fallback or settings.graph_backend.lower() == "csv":
        _backend_cache, _ACTIVE = csv_fallback, "csv"
        logger.info("patient_store: using CSV backend")
        return _backend_cache

    # Preferred path: Neo4j.
    try:
        from backend.knowledge_graph import neo4j_store
        if neo4j_store.ping():
            neo4j_store.init_schema()
            _backend_cache, _ACTIVE = neo4j_store, "neo4j"
            logger.info("patient_store: using Neo4j knowledge-graph backend")
            return _backend_cache
        raise ConnectionError("Neo4j not reachable")
    except Exception as e:  # noqa: BLE001
        if settings.allow_csv_fallback:
            logger.warning(f"patient_store: Neo4j unavailable ({e}); falling back to CSV")
            _backend_cache, _ACTIVE = csv_fallback, "csv"
            return _backend_cache
        raise


def active_backend() -> str:
    """Return 'neo4j' or 'csv' for the currently-selected backend."""
    _select_backend()
    return _ACTIVE


def reset_backend() -> None:
    """Clear the cached backend choice (e.g. after starting Neo4j)."""
    global _backend_cache, _ACTIVE
    _backend_cache, _ACTIVE = None, "unknown"


# ── Forwarded API ───────────────────────────────────────────────────────────────

def create_patient(name: str, dob: date, gender: str, notes: str = "") -> dict:
    return _select_backend().create_patient(name, dob, gender, notes)


def get_patient(patient_id: str) -> Optional[dict]:
    return _select_backend().get_patient(patient_id)


def list_patients() -> list[dict]:
    return _select_backend().list_patients()


def update_patient(patient_id: str, updates: dict) -> bool:
    return _select_backend().update_patient(patient_id, updates)


def create_visit(patient_id: str, notes: str = "") -> dict:
    return _select_backend().create_visit(patient_id, notes)


def get_visits(patient_id: str) -> list[dict]:
    return _select_backend().get_visits(patient_id)


def save_mri_scan(patient_id: str, visit_id: str, file_path: str,
                  slice_used: Optional[int] = None) -> dict:
    return _select_backend().save_mri_scan(patient_id, visit_id, file_path, slice_used)


def get_latest_scan(patient_id: str) -> Optional[dict]:
    return _select_backend().get_latest_scan(patient_id)


def get_scan_by_id(scan_id: str, patient_id: str) -> Optional[dict]:
    return _select_backend().get_scan_by_id(scan_id, patient_id)


def get_all_scans(patient_id: str) -> list[dict]:
    return _select_backend().get_all_scans(patient_id)


def delete_mri_scan(scan_id: str, patient_id: str) -> Optional[str]:
    return _select_backend().delete_mri_scan(scan_id, patient_id)


def save_synthetic_pet(patient_id: str, scan_id: str, file_path: str,
                       ssim_score: Optional[float] = None,
                       psnr_score: Optional[float] = None) -> dict:
    return _select_backend().save_synthetic_pet(patient_id, scan_id, file_path, ssim_score, psnr_score)


def save_clinical_features(patient_id: str, visit_id: str, features: dict) -> dict:
    return _select_backend().save_clinical_features(patient_id, visit_id, features)


def save_cognitive_test(patient_id: str, visit_id: str, scores: dict) -> dict:
    return _select_backend().save_cognitive_test(patient_id, visit_id, scores)


def get_cognitive_tests(patient_id: str) -> list[dict]:
    return _select_backend().get_cognitive_tests(patient_id)


def save_prediction(patient_id: str, visit_id: str, prediction: dict) -> dict:
    return _select_backend().save_prediction(patient_id, visit_id, prediction)


def get_predictions(patient_id: str) -> list[dict]:
    return _select_backend().get_predictions(patient_id)


def get_latest_prediction(patient_id: str) -> Optional[dict]:
    return _select_backend().get_latest_prediction(patient_id)


def save_digital_twin(patient_id: str, visit_id: str, twin_data: dict) -> dict:
    return _select_backend().save_digital_twin(patient_id, visit_id, twin_data)


def get_digital_twin(patient_id: str) -> Optional[dict]:
    return _select_backend().get_digital_twin(patient_id)


def save_report(patient_id: str, visit_id: str, file_path: str,
                source_type: str, extracted_fields: dict) -> dict:
    return _select_backend().save_report(patient_id, visit_id, file_path, source_type, extracted_fields)


def get_reports(patient_id: str) -> list[dict]:
    return _select_backend().get_reports(patient_id)
