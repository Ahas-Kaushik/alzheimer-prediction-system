"""Migrate all existing CSV records into the Neo4j knowledge graph.

Idempotent: every node is MERGEd on its primary key, so re-running will not
create duplicates. Run after `docker compose up -d`:

    python scripts/migrate_csv_to_neo4j.py

Reads from data/csv_db/*.csv and writes Patient + linked record nodes.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.knowledge_graph import csv_fallback, neo4j_client, neo4j_store  # noqa: E402
from backend.knowledge_graph.neo4j_store import _ENTITY, _session  # noqa: E402
from backend.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

# table → primary-key field
_PK = {
    "patients": "patient_id",
    "visits": "visit_id",
    "mri_scans": "scan_id",
    "synthetic_pets": "pet_id",
    "clinical_features": "feature_id",
    "cognitive_tests": "test_id",
    "predictions": "pred_id",
    "digital_twins": "twin_id",
    "reports": "report_id",
}


def migrate() -> dict[str, int]:
    if not neo4j_store.ping():
        raise SystemExit(
            "[ERROR] Neo4j is not reachable at the configured URI.\n"
            "        Start it first:  docker compose up -d   (then wait ~20s)"
        )

    neo4j_client.init_constraints()
    counts: dict[str, int] = {}

    # 1) Patients (graph hubs)
    patients = csv_fallback._read_table("patients")
    with _session() as s:
        for row in patients:
            pid = row.get("patient_id")
            if not pid:
                continue
            s.run("MERGE (p:Patient {patient_id:$pid}) SET p += $props", pid=pid, props=row)
    counts["patients"] = len(patients)
    logger.info(f"Migrated {len(patients)} patients")

    # 2) Child records linked to their Patient
    for table, (label, rel, _order) in _ENTITY.items():
        pk = _PK[table]
        rows = csv_fallback._read_table(table)
        n = 0
        with _session() as s:
            for row in rows:
                pid = row.get("patient_id")
                key = row.get(pk)
                if not pid or not key:
                    continue
                s.run(
                    f"MATCH (p:Patient {{patient_id:$pid}}) "
                    f"MERGE (c:{label} {{{pk}:$key}}) SET c += $props "
                    f"MERGE (p)-[:{rel}]->(c)",
                    pid=pid, key=key, props=row,
                )
                n += 1
        counts[table] = n
        logger.info(f"Migrated {n} {table}")

    return counts


if __name__ == "__main__":
    result = migrate()
    print("\n[OK] Migration complete:")
    for table, n in result.items():
        print(f"   {table:20s} {n}")
    total = sum(result.values())
    print(f"\n   Total nodes written: {total}")
    print("   Open http://localhost:7474 and run:  MATCH (n) RETURN n LIMIT 100")
