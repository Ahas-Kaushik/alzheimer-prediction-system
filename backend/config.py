from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    debug: bool = True

    # Neo4j (primary knowledge-graph backend)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    # Storage backend routing
    #   graph_backend = "neo4j"  → use Neo4j knowledge graph (preferred)
    #   graph_backend = "csv"    → use the CSV dev store directly
    graph_backend: str = "neo4j"
    # When True, transparently fall back to the CSV store if Neo4j is unreachable.
    allow_csv_fallback: bool = True
    # Legacy flag kept for backward compatibility; when True it forces the CSV backend.
    use_csv_fallback: bool = False

    # ── RAG / Vector storage ────────────────────────────────────────────────
    enable_rag: bool = True
    # Local sentence-transformers embedding model (no API key required).
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384
    # Name of the Neo4j native vector index over clinical knowledge chunks.
    vector_index_name: str = "clinical_chunks"
    rag_top_k: int = 4

    # ── LLM (Google Gemini) ─────────────────────────────────────────────────
    # Leave empty to use deterministic templated reasoning; set to enable Gemini.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"

    # Model checkpoints
    gan_checkpoint_path: str = "data/checkpoints/gan_generator.pth"
    classifier_checkpoint_path: str = "data/checkpoints/classifier.pth"
    resnet_extractor_checkpoint_path: str = "data/checkpoints/resnet_feature_extractor.pth"

    # Upload directory
    upload_dir: str = "backend/uploads"

    # GAN inference
    gan_image_size: int = 256
    gan_inference_device: str = "cuda"  # falls back to cpu if unavailable

    # Cognitive test
    cognitive_test_stimuli_count: int = 10
    cognitive_test_stimulus_duration_ms: int = 3000
    cognitive_test_isi_ms: int = 500

    # CSV fallback paths (relative to project root)
    csv_dir: str = "data/csv_db"

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def csv_dir_path(self) -> Path:
        return Path(self.csv_dir)

    @property
    def gan_checkpoint(self) -> Path:
        return Path(self.gan_checkpoint_path)

    @property
    def classifier_checkpoint(self) -> Path:
        return Path(self.classifier_checkpoint_path)

    @property
    def resnet_extractor_checkpoint(self) -> Path:
        return Path(self.resnet_extractor_checkpoint_path)


settings = Settings()
