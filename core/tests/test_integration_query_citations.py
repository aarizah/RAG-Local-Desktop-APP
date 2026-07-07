from pathlib import Path

from fastapi.testclient import TestClient

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


def test_query_returns_valid_citations_from_final_context(tmp_path: Path) -> None:
    db_path = tmp_path / "rag.db"
    s3_folder = tmp_path / "s3"
    s3_folder.mkdir(parents=True, exist_ok=True)
    source_path = s3_folder / "doc.pdf"
    source_path.write_text("La ley establece reglas de prueba documental.", encoding="utf-8")

    embedding = FakeEmbedding()
    vector_store = EmptyVectorStore()
    lexical = SqliteFtsRepository(db_path=str(db_path))
    ingestion = IngestionService(
        sqlite_path=str(db_path),
        chunker=SimpleChunkingAdapter(max_chars=120, overlap=0),
        embedding=embedding,
        vector_store=vector_store,
        lexical_store=lexical,
        s3_dir=str(s3_folder),
    )
    retrieval = RetrievalService(embedding=embedding, vector_store=vector_store, lexical_store=lexical)
    reranker = Reranker(RerankConfig())
    app = create_app(
        ingestion_service=ingestion,
        retrieval_service=retrieval,
        reranker=reranker,
        generation_service=FakeGeneration(),
    )
    client = TestClient(app)

    ingest_payload = IngestRequestV1(source_path="doc.pdf").model_dump()
    ingest_resp = client.post("/v1/ingest", json=ingest_payload)
    assert ingest_resp.status_code == 200

    query_payload = QueryRequestV1(query="prueba documental").model_dump()
    query_resp = client.post("/v1/query", json=query_payload)
    assert query_resp.status_code == 200
    body = query_resp.json()
    assert len(body["citations"]) >= 1
    assert "/" in body["citations"][0]
    retrieved = body.get("retrieved_chunks") or []
    assert len(retrieved) >= 1
    assert "text" in retrieved[0]
    assert len(retrieved[0]["text"]) >= 1
    assert "ref" in retrieved[0]
    legacy_chunks = body.get("chunks") or []
    assert len(legacy_chunks) == len(retrieved)
