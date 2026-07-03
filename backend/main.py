from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure upload directory exists
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    settings.csv_dir_path.mkdir(parents=True, exist_ok=True)

    # Report the active storage backend (Neo4j knowledge graph or CSV fallback).
    try:
        from backend.knowledge_graph import patient_store
        logger.info(f"Storage backend: {patient_store.active_backend()}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Could not determine storage backend: {e}")

    # Seed the RAG vector index if Neo4j is active and not yet populated, and
    # eagerly load the embedding model so `transformers` is fully imported in
    # the main thread. This avoids a concurrent-import race with the OCR warmup
    # thread (PaddleOCR also imports transformers).
    if settings.enable_rag:
        try:
            from backend.knowledge_graph import patient_store
            from backend.rag import embeddings, vector_store
            embeddings.get_model()  # fully initialises transformers/sentence-transformers
            if patient_store.active_backend() == "neo4j" and not vector_store.is_seeded():
                vector_store.seed_knowledge_base()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"RAG warmup/seeding skipped: {e}")

    # Warm up the OCR model in a background thread so the first blood-report
    # upload isn't slowed by model initialisation. Started AFTER the embedding
    # model is loaded so the two don't import `transformers` concurrently.
    try:
        import threading
        from backend.models.ocr.ocr_engine import warmup as _ocr_warmup
        threading.Thread(target=_ocr_warmup, daemon=True).start()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"OCR warmup thread not started: {e}")

    logger.info("Alzheimer Prediction System started")
    yield
    logger.info("Alzheimer Prediction System shutting down")


app = FastAPI(
    title="Alzheimer Prediction System API",
    description="Agent-Based Alzheimer Stage Prediction using MRI, Synthetic PET, and Clinical Reports",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static file serving for uploaded images
_uploads_dir = Path(settings.upload_dir)
_uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")

# Register all API routers
from backend.api.routes import cognitive, patient, prediction, rag, reports, scan, twin

app.include_router(patient.router, prefix="/api/patients", tags=["Patients"])
app.include_router(scan.router, prefix="/api/scans", tags=["Scans"])
app.include_router(prediction.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(cognitive.router, prefix="/api/cognitive", tags=["Cognitive Test"])
app.include_router(twin.router, prefix="/api/twin", tags=["Digital Twin"])
app.include_router(reports.router, prefix="/api/reports", tags=["Reports"])
app.include_router(rag.router, prefix="/api/rag", tags=["GraphRAG"])


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug,
    )
