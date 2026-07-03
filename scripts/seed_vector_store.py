"""Embed the clinical knowledge base into the Neo4j vector index.

Run after Neo4j is up and (optionally) after migrating patient data:

    python scripts/seed_vector_store.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.knowledge_graph import neo4j_store  # noqa: E402
from backend.rag import vector_store  # noqa: E402


if __name__ == "__main__":
    if not neo4j_store.ping():
        raise SystemExit(
            "[ERROR] Neo4j is not reachable. Start it first:  docker compose up -d"
        )
    n = vector_store.seed_knowledge_base()
    print(f"[OK] Seeded {n} clinical knowledge chunks into vector index "
          f"'{vector_store.settings.vector_index_name}'.")
