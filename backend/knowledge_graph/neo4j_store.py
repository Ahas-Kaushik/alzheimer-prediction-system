"""Neo4j knowledge-graph store.

Implements the exact same public API as ``csv_fallback`` so it is a drop-in
backend for ``patient_store``. Every record becomes a node linked to its
Patient (the graph hub); properties are stored as strings to mirror the CSV
store's behaviour so all downstream parsing (``_safe_float`` etc.) is identical.

Graph model
-----------
    (Patient)-[:HAS_VISIT]->(Visit)
    (Patient)-[:HAS_MRI]->(MRIScan)
    (Patient)-[:HAS_SYNTHETIC_PET]->(SyntheticPET)
    (Patient)-[:HAS_FEATURES]->(ClinicalFeatures)
    (Patient)-[:HAS_COGNITIVE_TEST]->(CognitiveTest)
    (Patient)-[:HAS_PREDICTION]->(Prediction)
    (Patient)-[:HAS_TWIN]->(DigitalTwin)
    (Patient)-[:HAS_REPORT]->(Report)
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Optional

from backend.config import settings
from backend.knowledge_graph import neo4j_client
from backend.knowledge_graph.csv_fallback import _TABLES, _now
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# table name → (node label, relationship from Patient, default order-by property)
_ENTITY = {
    "visits":            ("Visit", "HAS_VISIT", "visit_date"),
    "mri_scans":         ("MRIScan", "HAS_MRI", "upload_date"),
    "synthetic_pets":    ("SyntheticPET", "HAS_SYNTHETIC_PET", "generated_at"),
    "clinical_features": ("ClinicalFeatures", "HAS_FEATURES", None),
    "cognitive_tests":   ("CognitiveTest", "HAS_COGNITIVE_TEST", "run_date"),
    "predictions":       ("Prediction", "HAS_PREDICTION", "run_date"),
    "digital_twins":     ("DigitalTwin", "HAS_TWIN", "generated_at"),
    "reports":           ("Report", "HAS_REPORT", "upload_date"),
}


# ── low-level helpers ───────────────────────────────────────────────────────────

def _session():
    driver = neo4j_client.get_driver()
    return driver.session(database=settings.neo4j_database)


def _stringify(row: dict[str, Any], cols: list[str]) -> dict[str, str]:
    """Coerce to the CSV-compatible {col: str} shape (missing → '')."""
    return {c: ("" if row.get(c) is None else str(row.get(c))) for c in cols}


def ping() -> bool:
    """Return True if Neo4j is reachable."""
    try:
        neo4j_client.get_driver().verify_connectivity()
        return True
    except Exception:
        return False


def init_schema() -> None:
    """Create uniqueness constraints (idempotent)."""
    neo4j_client.init_constraints()


def _create_child(table: str, patient_id: str, props: dict[str, Any]) -> dict:
    label, rel, _ = _ENTITY[table]
    cols = _TABLES[table]
    row = _stringify({**props, "patient_id": patient_id}, cols)
    cypher = (
        f"MERGE (p:Patient {{patient_id: $patient_id}}) "
        f"CREATE (c:{label}) SET c = $props "
        f"CREATE (p)-[:{rel}]->(c) "
        f"RETURN c"
    )
    with _session() as s:
        rec = s.run(cypher, patient_id=patient_id, props=row).single()
        return dict(rec["c"]) if rec else row


def _list_children(table: str, patient_id: str) -> list[dict]:
    label, rel, order_by = _ENTITY[table]
    cypher = f"MATCH (:Patient {{patient_id: $pid}})-[:{rel}]->(c:{label}) RETURN c"
    if order_by:
        cypher += f" ORDER BY c.{order_by}"
    with _session() as s:
        return [dict(r["c"]) for r in s.run(cypher, pid=patient_id)]


# ── Patients ────────────────────────────────────────────────────────────────────

def create_patient(name: str, dob: date, gender: str, notes: str = "") -> dict:
    patient_id = f"PAT-{uuid.uuid4().hex[:8].upper()}"
    row = {
        "patient_id": patient_id, "name": name, "dob": str(dob),
        "gender": gender, "created_at": _now(), "notes": notes,
    }
    with _session() as s:
        s.run("CREATE (p:Patient) SET p = $props", props=row)
    logger.info(f"Neo4j: created patient {patient_id}")
    return row


def get_patient(patient_id: str) -> Optional[dict]:
    with _session() as s:
        rec = s.run("MATCH (p:Patient {patient_id: $pid}) RETURN p", pid=patient_id).single()
        return dict(rec["p"]) if rec else None


def list_patients() -> list[dict]:
    with _session() as s:
        return [dict(r["p"]) for r in s.run("MATCH (p:Patient) RETURN p ORDER BY p.created_at")]


def update_patient(patient_id: str, updates: dict) -> bool:
    clean = {k: str(v) for k, v in updates.items()}
    with _session() as s:
        rec = s.run(
            "MATCH (p:Patient {patient_id: $pid}) SET p += $u RETURN p",
            pid=patient_id, u=clean,
        ).single()
        return rec is not None


# ── Visits ──────────────────────────────────────────────────────────────────────

def create_visit(patient_id: str, notes: str = "") -> dict:
    visit_id = f"VIS-{uuid.uuid4().hex[:8].upper()}"
    props = {"visit_id": visit_id, "patient_id": patient_id, "visit_date": _now(), "notes": notes}
    return _create_child("visits", patient_id, props)


def get_visits(patient_id: str) -> list[dict]:
    return _list_children("visits", patient_id)


# ── MRI scans ───────────────────────────────────────────────────────────────────

def save_mri_scan(patient_id: str, visit_id: str, file_path: str,
                  slice_used: Optional[int] = None) -> dict:
    scan_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
    props = {
        "scan_id": scan_id, "visit_id": visit_id, "patient_id": patient_id,
        "file_path": file_path, "upload_date": _now(),
        "slice_used": str(slice_used) if slice_used is not None else "",
    }
    return _create_child("mri_scans", patient_id, props)


def get_latest_scan(patient_id: str) -> Optional[dict]:
    scans = _list_children("mri_scans", patient_id)
    return scans[-1] if scans else None


def get_scan_by_id(scan_id: str, patient_id: str) -> Optional[dict]:
    for r in _list_children("mri_scans", patient_id):
        if r.get("scan_id") == scan_id:
            return r
    return None


def get_all_scans(patient_id: str) -> list[dict]:
    return _list_children("mri_scans", patient_id)


def delete_mri_scan(scan_id: str, patient_id: str) -> Optional[str]:
    with _session() as s:
        rec = s.run(
            "MATCH (:Patient {patient_id: $pid})-[:HAS_MRI]->(c:MRIScan {scan_id: $sid}) "
            "WITH c, c.file_path AS fp DETACH DELETE c RETURN fp",
            pid=patient_id, sid=scan_id,
        ).single()
        return rec["fp"] if rec else None


# ── Synthetic PET ───────────────────────────────────────────────────────────────

def save_synthetic_pet(patient_id: str, scan_id: str, file_path: str,
                       ssim_score: Optional[float] = None,
                       psnr_score: Optional[float] = None) -> dict:
    pet_id = f"PET-{uuid.uuid4().hex[:8].upper()}"
    props = {
        "pet_id": pet_id, "scan_id": scan_id, "patient_id": patient_id,
        "file_path": file_path, "generated_at": _now(),
        "ssim_score": str(ssim_score) if ssim_score is not None else "",
        "psnr_score": str(psnr_score) if psnr_score is not None else "",
    }
    return _create_child("synthetic_pets", patient_id, props)


# ── Clinical features ───────────────────────────────────────────────────────────

def save_clinical_features(patient_id: str, visit_id: str, features: dict) -> dict:
    feature_id = f"FTR-{uuid.uuid4().hex[:8].upper()}"
    props = {"feature_id": feature_id, "visit_id": visit_id, "patient_id": patient_id}
    props.update({k: ("" if v is None else str(v)) for k, v in features.items()})
    return _create_child("clinical_features", patient_id, props)


# ── Cognitive tests ─────────────────────────────────────────────────────────────

def save_cognitive_test(patient_id: str, visit_id: str, scores: dict) -> dict:
    test_id = f"COG-{uuid.uuid4().hex[:8].upper()}"
    props = {"test_id": test_id, "visit_id": visit_id, "patient_id": patient_id, "run_date": _now()}
    props.update({k: str(v) for k, v in scores.items()})
    return _create_child("cognitive_tests", patient_id, props)


def get_cognitive_tests(patient_id: str) -> list[dict]:
    return _list_children("cognitive_tests", patient_id)


# ── Predictions ─────────────────────────────────────────────────────────────────

def save_prediction(patient_id: str, visit_id: str, prediction: dict) -> dict:
    pred_id = f"PRD-{uuid.uuid4().hex[:8].upper()}"
    props = {"pred_id": pred_id, "visit_id": visit_id, "patient_id": patient_id, "run_date": _now()}
    props.update({k: str(v) for k, v in prediction.items()})
    return _create_child("predictions", patient_id, props)


def get_predictions(patient_id: str) -> list[dict]:
    return _list_children("predictions", patient_id)


def get_latest_prediction(patient_id: str) -> Optional[dict]:
    preds = get_predictions(patient_id)
    return preds[-1] if preds else None


# ── Digital twin ────────────────────────────────────────────────────────────────

def save_digital_twin(patient_id: str, visit_id: str, twin_data: dict) -> dict:
    twin_id = f"TWN-{uuid.uuid4().hex[:8].upper()}"
    props = {
        "twin_id": twin_id, "visit_id": visit_id, "patient_id": patient_id,
        "generated_at": _now(),
        "neuron_connectivity": str(twin_data.get("neuron_connectivity", 1.0)),
        "delta_from_last": twin_data.get("delta_from_last", "stable"),
        "regions_json": str(twin_data.get("regions", [])),
    }
    return _create_child("digital_twins", patient_id, props)


def get_digital_twin(patient_id: str) -> Optional[dict]:
    twins = _list_children("digital_twins", patient_id)
    return twins[-1] if twins else None


# ── Reports ─────────────────────────────────────────────────────────────────────

def save_report(patient_id: str, visit_id: str, file_path: str,
                source_type: str, extracted_fields: dict) -> dict:
    import json
    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    props = {
        "report_id": report_id, "visit_id": visit_id, "patient_id": patient_id,
        "file_path": file_path, "upload_date": _now(), "source_type": source_type,
        "extracted_fields_json": json.dumps(extracted_fields),
    }
    return _create_child("reports", patient_id, props)


def get_reports(patient_id: str) -> list[dict]:
    return _list_children("reports", patient_id)
