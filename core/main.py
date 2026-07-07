from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import uvicorn

from src.api import create_app
from src.config import get_settings
from src.observability import configure_logging
from src.rag.chunking import DoclingPdfChunkingAdapter
from src.rag.embedding import SentenceTransformersEmbeddingAdapter
from src.rag.generation import LlamaCppGenerationAdapter
from src.rag.ingestion import IngestionService
from src.rag.rerank import RerankConfig, Reranker
from src.rag.retrieval import RetrievalService
from src.stores.lexical_store import SqliteFtsRepository
from src.stores.vector_store import ChromaVectorRepository


def build_app():
    settings = get_settings()
    configure_logging(json_logs=settings.log_json)

    if not settings.llamacpp_model_path:
        raise RuntimeError(
            "No GGUF model available. Set LLAMACPP_MODEL_PATH or place a .gguf file in ../models"
        )

    model_path = Path(settings.llamacpp_model_path)
    if not model_path.exists() or model_path.suffix.lower() != ".gguf":
        raise RuntimeError(
            f"Invalid GGUF model path: '{settings.llamacpp_model_path}'. "
            "Set LLAMACPP_MODEL_PATH to an existing .gguf file or place one in ../models"
        )

    chunker = DoclingPdfChunkingAdapter(
        tokenizer_model_id=settings.chunking_tokenizer_model_id,
        max_tokens=settings.chunking_max_tokens,
    )
    embedding = SentenceTransformersEmbeddingAdapter(
        model_id=settings.embedding_model_id,
        device=settings.embedding_device,
    )
    vector_store = ChromaVectorRepository(
        persist_dir=settings.chroma_persist_dir,
        collection_name=settings.chroma_collection,
        distance=settings.chroma_distance,
    )
    lexical_store = SqliteFtsRepository(
        db_path=settings.sqlite_path,
        table_name=settings.fts_table,
        tokenizer=settings.fts_tokenizer,
    )
    ingestion_service = IngestionService(
        sqlite_path=settings.sqlite_path,
        chunker=chunker,
        embedding=embedding,
        vector_store=vector_store,
        lexical_store=lexical_store,
        s3_dir=str(Path(settings.s3_dir).resolve()),
    )
    retrieval_service = RetrievalService(
        embedding=embedding,
        vector_store=vector_store,
        lexical_store=lexical_store,
        semantic_threshold=settings.rag_semantic_threshold,
        rrf_k=settings.rag_rrf_k,
    )
    reranker = Reranker(
        RerankConfig(
            strategy=settings.rerank_strategy,
            lambda_mult=settings.mmr_lambda,
            cross_encoder_enabled=settings.cross_encoder_enabled,
            cross_encoder_model_id=settings.cross_encoder_model_id,
        )
    )
    generation = LlamaCppGenerationAdapter(
        model_path=str(model_path.resolve()),
        n_ctx=settings.llamacpp_n_ctx,
        n_threads=settings.llamacpp_n_threads,
        n_gpu_layers=settings.llamacpp_n_gpu_layers,
        max_tokens=settings.llamacpp_max_tokens,
        temperature=settings.llamacpp_temperature,
    )

    return create_app(
        ingestion_service=ingestion_service,
        retrieval_service=retrieval_service,
        reranker=reranker,
        generation_service=generation,
    )


app = build_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
