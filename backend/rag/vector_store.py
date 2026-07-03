"""Vector storage backed by Neo4j's native vector index.

Knowledge chunks are stored as ``(:KnowledgeChunk)`` nodes with an ``embedding``
property; similarity search uses ``db.index.vector.queryNodes``. This keeps the
vector store *inside* the knowledge graph rather than in a separate service.
"""
from __future__ import annotations

from typing import List

from backend.config import settings
from backend.knowledge_graph import neo4j_store
from backend.rag import embeddings
from backend.rag.knowledge_base import KNOWLEDGE_CHUNKS
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def ensure_vector_index() -> None:
    """Create the vector index over KnowledgeChunk.embedding (idempotent)."""
    name = settings.vector_index_name
    cypher = (
        f"CREATE VECTOR INDEX {name} IF NOT EXISTS "
        f"FOR (c:KnowledgeChunk) ON (c.embedding) "
        f"OPTIONS {{indexConfig: {{"
        f"`vector.dimensions`: {settings.embedding_dim}, "
        f"`vector.similarity_function`: 'cosine'}}}}"
    )
    with neo4j_store._session() as s:
        s.run(cypher)
    logger.info(f"Vector index '{name}' ensured ({settings.embedding_dim}-dim, cosine)")


def seed_knowledge_base() -> int:
    """Embed and upsert all knowledge chunks into the graph. Returns count."""
    ensure_vector_index()
    texts = [f"{c['title']}. {c['text']}" for c in KNOWLEDGE_CHUNKS]
    vectors = embeddings.embed_batch(texts)
    with neo4j_store._session() as s:
        for chunk, vec in zip(KNOWLEDGE_CHUNKS, vectors):
            s.run(
                "MERGE (c:KnowledgeChunk {id: $id}) "
                "SET c.title = $title, c.category = $category, c.text = $text, "
                "    c.embedding = $embedding",
                id=chunk["id"], title=chunk["title"], category=chunk["category"],
                text=chunk["text"], embedding=vec,
            )
    logger.info(f"Seeded {len(KNOWLEDGE_CHUNKS)} knowledge chunks into vector index")
    return len(KNOWLEDGE_CHUNKS)


def search(query: str, k: int | None = None) -> List[dict]:
    """Return the top-k most similar knowledge chunks to the query text."""
    k = k or settings.rag_top_k
    qvec = embeddings.embed_text(query)
    cypher = (
        "CALL db.index.vector.queryNodes($index, $k, $vec) "
        "YIELD node, score "
        "RETURN node.title AS title, node.category AS category, "
        "       node.text AS text, score ORDER BY score DESC"
    )
    try:
        with neo4j_store._session() as s:
            return [dict(r) for r in s.run(cypher, index=settings.vector_index_name, k=k, vec=qvec)]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Vector search failed ({e}); returning no context")
        return []


def project_2d() -> list[dict]:
    """Project the stored knowledge-chunk embeddings to 2D (PCA) for plotting.

    Returns a list of {title, category, x, y}. Empty list if not seeded /
    Neo4j unavailable.
    """
    try:
        with neo4j_store._session() as s:
            rows = [
                dict(r) for r in s.run(
                    "MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL "
                    "RETURN c.title AS title, c.category AS category, c.embedding AS embedding"
                )
            ]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Vector projection unavailable ({e})")
        return []

    if len(rows) < 2:
        return []

    import numpy as np
    from sklearn.decomposition import PCA

    X = np.array([r["embedding"] for r in rows], dtype=float)
    coords = PCA(n_components=2, random_state=42).fit_transform(X)
    # Normalise to a friendly plotting range.
    coords = coords - coords.mean(axis=0)
    span = np.abs(coords).max() or 1.0
    coords = coords / span
    return [
        {"title": r["title"], "category": r["category"],
         "x": round(float(coords[i][0]), 4), "y": round(float(coords[i][1]), 4)}
        for i, r in enumerate(rows)
    ]


def vector_overview() -> dict:
    """Return a formal view of the vector store: the actual stored vectors as a
    table (norm + value preview), a cosine-similarity matrix, and a 2D PCA
    projection — for inspecting the embeddings like a real vector database.
    """
    try:
        with neo4j_store._session() as s:
            rows = [
                dict(r) for r in s.run(
                    "MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL "
                    "RETURN c.id AS id, c.title AS title, c.category AS category, "
                    "       c.embedding AS embedding ORDER BY c.category, c.title"
                )
            ]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Vector overview unavailable ({e})")
        rows = []

    empty = {"points": [], "chunks": [], "similarity": [], "labels": [],
             "dim": settings.embedding_dim, "count": 0}
    if len(rows) < 2:
        return empty

    import numpy as np
    from sklearn.decomposition import PCA

    X = np.array([r["embedding"] for r in rows], dtype=float)
    norms = np.linalg.norm(X, axis=1)

    # 2D PCA projection (normalised to a friendly plotting range).
    coords = PCA(n_components=2, random_state=42).fit_transform(X)
    coords = coords - coords.mean(axis=0)
    span = np.abs(coords).max() or 1.0
    coords = coords / span

    # Cosine-similarity matrix.
    Xn = X / (norms[:, None] + 1e-9)
    sim = (Xn @ Xn.T)

    chunks = [
        {
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "norm": round(float(norms[i]), 4),
            "preview": [round(float(v), 4) for v in X[i][:8]],
        }
        for i, r in enumerate(rows)
    ]
    points = [
        {"title": r["title"], "category": r["category"],
         "x": round(float(coords[i][0]), 4), "y": round(float(coords[i][1]), 4)}
        for i, r in enumerate(rows)
    ]
    labels = [r["title"] for r in rows]
    return {
        "points": points,
        "chunks": chunks,
        "similarity": [[round(float(v), 3) for v in row] for row in sim],
        "labels": labels,
        "dim": int(X.shape[1]),
        "count": len(rows),
    }


def is_seeded() -> bool:
    """True if at least one embedded knowledge chunk exists."""
    try:
        with neo4j_store._session() as s:
            rec = s.run(
                "MATCH (c:KnowledgeChunk) WHERE c.embedding IS NOT NULL "
                "RETURN count(c) AS n"
            ).single()
            return bool(rec and rec["n"] > 0)
    except Exception:
        return False
