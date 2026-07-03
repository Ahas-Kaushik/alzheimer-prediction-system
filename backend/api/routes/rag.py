from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings
from backend.knowledge_graph import patient_store
from backend.llm import gemini_client
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class AskIn(BaseModel):
    patient_id: str
    question: str


@router.get("/status")
async def rag_status() -> dict:
    """Report the active architecture: storage backend, vector store, LLM."""
    seeded = False
    if settings.enable_rag:
        try:
            from backend.rag import vector_store
            seeded = vector_store.is_seeded()
        except Exception:
            seeded = False
    return {
        "storage_backend": patient_store.active_backend(),   # 'neo4j' | 'csv'
        "rag_enabled": settings.enable_rag,
        "vector_index": settings.vector_index_name,
        "vector_store_seeded": seeded,
        "embedding_model": settings.embedding_model_name,
        "llm_provider": "gemini" if gemini_client.is_enabled() else "templated-fallback",
        "llm_model": settings.gemini_model if gemini_client.is_enabled() else None,
    }


@router.post("/seed")
async def seed_vector_store() -> dict:
    """(Re)embed the clinical knowledge base into the Neo4j vector index."""
    try:
        from backend.rag import vector_store
        n = vector_store.seed_knowledge_base()
        return {"seeded_chunks": n, "index": settings.vector_index_name}
    except Exception as e:
        logger.error(f"seed failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask")
async def ask(body: AskIn) -> dict:
    """Answer a free-text question about a patient using GraphRAG."""
    try:
        from backend.rag import graph_rag
        return graph_rag.answer_question(body.patient_id, body.question)
    except Exception as e:
        logger.error(f"ask failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph")
async def knowledge_graph_snapshot(cap: int = 3) -> dict:
    """Compact node-link snapshot of the patient knowledge graph for the UI."""
    try:
        from backend.knowledge_graph import graph_viz
        return graph_viz.get_graph_snapshot(cap=cap)
    except Exception as e:
        logger.error(f"graph snapshot failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vectors")
async def vector_projection() -> dict:
    """2D PCA projection of the knowledge-chunk embeddings for a scatter plot."""
    try:
        from backend.rag import vector_store
        points = vector_store.project_2d()
        return {
            "points": points,
            "index": settings.vector_index_name,
            "dim": settings.embedding_dim,
            "embedding_model": settings.embedding_model_name,
            "count": len(points),
        }
    except Exception as e:
        logger.error(f"vector projection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explain/{patient_id}")
async def explain(patient_id: str) -> dict:
    """Grounded clinical explanation of the patient's latest predicted stage."""
    try:
        from backend.rag import graph_rag
        return graph_rag.explain_prediction(patient_id)
    except Exception as e:
        logger.error(f"explain failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
