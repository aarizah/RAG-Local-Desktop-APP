from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_host: str = Field(default="127.0.0.1", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_timeout_s: int = Field(default=30, alias="API_TIMEOUT_S")

    chroma_persist_dir: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIR")
    chroma_collection: str = Field(default="local_rag_chunks", alias="CHROMA_COLLECTION")
    chroma_distance: str = Field(default="cosine", alias="CHROMA_DISTANCE")

    sqlite_path: str = Field(default="./data/rag.db", alias="SQLITE_PATH")
    s3_dir: str = Field(
        default="./s3",
        alias="S3_DIR",
    )
    fts_table: str = Field(default="chunks_fts", alias="FTS_TABLE")
    fts_tokenizer: str = Field(default="unicode61", alias="FTS_TOKENIZER")

    chunking_tokenizer_model_id: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="CHUNKING_TOKENIZER_MODEL_ID",
    )
    chunking_max_tokens: int = Field(default=256, alias="CHUNKING_MAX_TOKENS")

    embedding_model_id: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL_ID"
    )
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")

    rag_candidate_k: int = Field(default=30, alias="RAG_CANDIDATE_K")
    rag_rerank_k: int = Field(default=10, alias="RAG_RERANK_K")
    rag_final_k: int = Field(default=5, alias="RAG_FINAL_K")
    rag_semantic_threshold: float = Field(default=0.0, alias="RAG_SEMANTIC_THRESHOLD")
    rag_rrf_k: int = Field(default=60, alias="RAG_RRF_K")
    rerank_strategy: str = Field(default="cross_encoder", alias="RERANK_STRATEGY")
    mmr_lambda: float = Field(default=0.5, alias="MMR_LAMBDA")
    cross_encoder_enabled: bool = Field(default=False, alias="CROSS_ENCODER_ENABLED")
    cross_encoder_model_id: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        alias="CROSS_ENCODER_MODEL_ID",
    )

    llamacpp_model_path: str = Field(default="", alias="LLAMACPP_MODEL_PATH")
    llamacpp_n_ctx: int = Field(default=4096, alias="LLAMACPP_N_CTX")
    llamacpp_n_threads: int = Field(default=4, alias="LLAMACPP_N_THREADS")
    llamacpp_n_gpu_layers: int = Field(default=0, alias="LLAMACPP_N_GPU_LAYERS")
    llamacpp_max_tokens: int = Field(default=512, alias="LLAMACPP_MAX_TOKENS")
    llamacpp_temperature: float = Field(default=0.0, alias="LLAMACPP_TEMPERATURE")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=True, alias="LOG_JSON")
    prometheus_enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")
    pii_redaction_enabled: bool = Field(default=True, alias="PII_REDACTION_ENABLED")

    @model_validator(mode="after")
    def validate_k_chain(self) -> "Settings":
        if self.rag_final_k > self.rag_rerank_k:
            raise ValueError("RAG_FINAL_K must be <= RAG_RERANK_K")
        if self.rag_rerank_k > self.rag_candidate_k:
            raise ValueError("RAG_RERANK_K must be <= RAG_CANDIDATE_K")
        if not self.llamacpp_model_path:
            self.llamacpp_model_path = detect_default_gguf_model_path()
        return self


# Default LLM path when LLAMACPP_MODEL_PATH is unset: first *.gguf under models_dir
# (default <repo>/models), lexicographically sorted; "" if the directory has no .gguf files.
def detect_default_gguf_model_path(models_dir: Path | None = None) -> str:
    models_dir = models_dir or (Path(__file__).resolve().parents[1] / "models")
    gguf_files = sorted(models_dir.glob("*.gguf"))
    if not gguf_files:
        return ""
    return str(gguf_files[0].resolve())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
