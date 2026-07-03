"""Local text embeddings via sentence-transformers (no API key required)."""
from __future__ import annotations

from typing import List

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_model = None


def get_model():
    """Lazy-load the embedding model (first call downloads it once, ~90 MB)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model {settings.embedding_model_name} …")
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def embed_text(text: str) -> List[float]:
    """Return a single embedding vector for a piece of text."""
    vec = get_model().encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Return embedding vectors for a batch of texts."""
    vecs = get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]
