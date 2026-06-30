from __future__ import annotations

from typing import Any, Optional

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_driver = None


def get_driver():
    """Return a singleton Neo4j driver, creating it on first call."""
    global _driver
    if _driver is None:
        try:
            from neo4j import GraphDatabase
            _driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            _driver.verify_connectivity()
            logger.info("Neo4j driver connected")
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            raise
    return _driver


def close_driver() -> None:
    global _driver
    if _driver:
        _driver.close()
        _driver = None


def run_query(cypher: str, params: Optional[dict[str, Any]] = None) -> list[dict]:
    """Execute a Cypher query and return a list of record dicts."""
    driver = get_driver()
    params = params or {}
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(cypher, **params)
        return [dict(record) for record in result]


def run_write(cypher: str, params: Optional[dict[str, Any]] = None) -> None:
    """Execute a write transaction."""
    driver = get_driver()
    params = params or {}
    with driver.session(database=settings.neo4j_database) as session:
        session.execute_write(lambda tx: tx.run(cypher, **params))


def init_constraints() -> None:
    """Apply all schema constraints (idempotent)."""
    from backend.knowledge_graph.graph_schema import CONSTRAINT_QUERIES
    driver = get_driver()
    with driver.session(database=settings.neo4j_database) as session:
        for query in CONSTRAINT_QUERIES:
            try:
                session.run(query)
            except Exception as e:
                logger.warning(f"Constraint creation skipped: {e}")
    logger.info("Neo4j constraints initialized")
