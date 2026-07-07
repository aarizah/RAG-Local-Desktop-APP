from pathlib import Path

from fastapi.testclient import TestClient

import src.api as api_module
from src.api import create_app
from src.contracts import IngestRequestV1, QueryRequestV1
from src.rag.ingestion import IngestionService
from src.rag.rerank import RerankConfig, Reranker
from src.rag.retrieval import RetrievalService
from src.stores.lexical_store import SqliteFtsRepository
from src.stores.vector_store import VectorRecord
from tests.fakes.chunking import SimpleChunkingAdapter


class FakeEmbedding:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t))] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class EmptyVectorStore:
    def upsert(self, records: list[VectorRecord]) -> None:
        return None

    def search(self, query_embedding: list[float], limit: int):
        return []


class FakeGeneration:
    def generate(self, *, question, contexts, correlation_id):
        citation = contexts[0][0].citation if contexts else "none"
        return f"respuesta [{citation}]"


class CapturingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def info(self, event: str, **kwargs) -> None:
        self.events.append((event, kwargs))


def test_query_logging_reports_stage_times_correlation_and_redacts_pii(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "rag.db"
    s3_folder = tmp_path / "s3"
    s3_folder.mkdir(parents=True, exist_ok=True)
    source_path = s3_folder / "doc.pdf"
    source_path.write_text("El procedimiento requiere prueba documental.", encoding="utf-8")

    logger = CapturingLogger()
    monkeypatch.setattr(api_module, "get_logger", lambda: logger)

    embedding = FakeEmbedding()
    vector_store = EmptyVectorStore()
    lexical = SqliteFtsRepository(db_path=str(db_path))

    app = create_app(
        ingestion_service=IngestionService(
            sqlite_path=str(db_path),
            chunker=SimpleChunkingAdapter(max_chars=120, overlap=0),
            embedding=embedding,
            vector_store=vector_store,
            lexical_store=lexical,
            s3_dir=str(s3_folder),
        ),
        retrieval_service=RetrievalService(
            embedding=embedding,
            vector_store=vector_store,
            lexical_store=lexical,
        ),
        reranker=Reranker(RerankConfig()),
        generation_service=FakeGeneration(),
    )
    client = TestClient(app)

    ingest_payload = IngestRequestV1(source_path="doc.pdf").model_dump()
    assert client.post("/v1/ingest", json=ingest_payload).status_code == 200

    query_payload = QueryRequestV1(query="DNI 12345678 en prueba documental").model_dump()
    resp = client.post("/v1/query", json=query_payload)
    assert resp.status_code == 200

    assert len(logger.events) == 1
    event_name, event_payload = logger.events[0]

    assert event_name == "query_completed"
    assert event_payload["status"] == "ok"
    assert event_payload["correlation_id"]
    assert event_payload["retrieval_ms"] >= 0
    assert event_payload["rerank_ms"] >= 0
    assert event_payload["generation_ms"] >= 0
    assert event_payload["total_ms"] >= 0
    assert event_payload["query"] == "DNI [REDACTED] en prueba documental"
    assert "12345678" not in event_payload["query"]
