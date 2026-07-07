import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.contracts import IngestRequestV1
from src.rag.chunking import Chunk
from src.rag.ingestion import DuplicateDocumentError, IngestionService
from src.rag.retrieval import RetrievalService
from src.stores.lexical_store import SqliteFtsRepository
from src.stores.vector_store import ChromaVectorRepository
from src.stores.vector_store import VectorRecord


class FakeEmbedding:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t))] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class FakePdfChunker:
    def chunk(self, *, document_id: str, version: int, source_path: str) -> list[Chunk]:
        source = Path(source_path)
        payload = source.read_bytes().decode("utf-8", errors="ignore")
        return [
            Chunk(
                document_id=document_id,
                version=version,
                chunk_id=f"v{version}-c0001",
                source_path=str(source),
                source_file=source.name,
                pages=[1],
                first_page=1,
                headings=["Resumen"],
                created_at="2026-01-01T00:00:00+00:00",
                text=payload,
            )
        ]


class InMemoryVectorStore:
    def __init__(self):
        self.records: list[VectorRecord] = []

    def upsert(self, records: list[VectorRecord]) -> None:
        self.records.extend(records)

    def search(self, query_embedding: list[float], limit: int):
        return []


class DummyRetrieval:
    def retrieve(self, *, query: str, candidate_k: int):
        return []


class DummyReranker:
    def rerank(self, candidates, rerank_k: int, final_k: int):
        return []


class DummyGeneration:
    def generate(self, *, question, contexts, correlation_id):
        return "ok"


def _write_fake_pdf(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _build_service(tmp_path: Path) -> IngestionService:
    db_path = tmp_path / "rag.db"
    s3_folder = tmp_path / "s3"
    s3_folder.mkdir(parents=True, exist_ok=True)
    return IngestionService(
        sqlite_path=str(db_path),
        chunker=FakePdfChunker(),
        embedding=FakeEmbedding(),
        vector_store=InMemoryVectorStore(),
        lexical_store=SqliteFtsRepository(db_path=str(db_path)),
        s3_dir=str(s3_folder),
    )


def _build_client(tmp_path: Path) -> TestClient:
    ingestion = _build_service(tmp_path)
    app = create_app(
        ingestion_service=ingestion,
        retrieval_service=DummyRetrieval(),
        reranker=DummyReranker(),
        generation_service=DummyGeneration(),
    )
    return TestClient(app)


def test_ingestion_generates_document_id_from_pdf_sha256(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    source_path = tmp_path / "s3" / "doc.pdf"
    pdf_bytes = ("hola mundo " * 100).encode("utf-8")
    source_path.write_bytes(pdf_bytes)

    response = service.ingest(IngestRequestV1(source_path="doc.pdf"))
    expected_document_id = hashlib.sha256(pdf_bytes).hexdigest()

    assert response.results[0].status == "indexed"
    assert response.results[0].document_id == expected_document_id
    assert response.results[0].content_hash == expected_document_id


def test_ingestion_rejects_duplicate_content_hash(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    source_path = tmp_path / "s3" / "doc.pdf"
    _write_fake_pdf(source_path, "contenido duplicado")

    service.ingest(IngestRequestV1(source_path="doc.pdf"))

    with pytest.raises(DuplicateDocumentError, match="Document already exists"):
        service.ingest(IngestRequestV1(source_path="doc.pdf"))


def test_ingestion_rejects_paths_outside_s3(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    with pytest.raises(ValueError, match="outside s3"):
        service.ingest(IngestRequestV1(source_path="../evil.pdf"))


def test_ingest_api_rejects_inline_content(tmp_path: Path) -> None:
    source_path = tmp_path / "s3" / "doc.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    _write_fake_pdf(source_path, "contenido")

    client = _build_client(tmp_path)
    resp = client.post(
        "/v1/ingest",
        json={
            "source_path": "doc.pdf",
            "content": "NO",
        },
    )
    assert resp.status_code == 422


def test_ingest_api_rejects_path_traversal(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    resp = client.post(
        "/v1/ingest",
        json={
            "source_path": "../outside.pdf",
        },
    )
    assert resp.status_code == 400


def test_ingest_api_maps_duplicate_to_http_409(tmp_path: Path) -> None:
    source_path = tmp_path / "s3" / "doc.pdf"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    _write_fake_pdf(source_path, "contenido ya indexado")

    client = _build_client(tmp_path)
    assert client.post("/v1/ingest", json={"source_path": "doc.pdf"}).status_code == 200

    resp = client.post("/v1/ingest", json={"source_path": "doc.pdf"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "DUPLICATE_DOCUMENT"


def test_ingest_batch_with_new_and_duplicate_is_atomic_and_returns_409(tmp_path: Path) -> None:
    s3_folder = tmp_path / "s3"
    s3_folder.mkdir(parents=True, exist_ok=True)
    _write_fake_pdf(s3_folder / "existing.pdf", "contenido duplicado existente")
    _write_fake_pdf(s3_folder / "new.pdf", "contenido nuevo")

    client = _build_client(tmp_path)
    assert client.post("/v1/ingest", json={"source_path": "existing.pdf"}).status_code == 200

    batch_resp = client.post(
        "/v1/ingest",
        json={"source_paths": ["new.pdf", "existing.pdf"]},
    )
    assert batch_resp.status_code == 409

    retry_new = client.post("/v1/ingest", json={"source_path": "new.pdf"})
    assert retry_new.status_code == 200


def test_chroma_persistence_survives_service_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "rag.db"
    chroma_dir = tmp_path / "chroma"
    s3_folder = tmp_path / "s3"
    s3_folder.mkdir(parents=True, exist_ok=True)
    source_path = s3_folder / "doc-restart.pdf"
    _write_fake_pdf(source_path, "persistencia chroma reinicio servicio retrieval local rag")

    embedding = FakeEmbedding()

    ingestion_service = IngestionService(
        sqlite_path=str(db_path),
        chunker=FakePdfChunker(),
        embedding=embedding,
        vector_store=ChromaVectorRepository(
            persist_dir=str(chroma_dir),
            collection_name="test_local_rag_chunks",
        ),
        lexical_store=SqliteFtsRepository(db_path=str(db_path)),
        s3_dir=str(s3_folder),
    )

    indexed = ingestion_service.ingest(
        IngestRequestV1(source_path="doc-restart.pdf")
    )
    assert indexed.results[0].status == "indexed"
    assert indexed.results[0].version == 1
    expected_document_id = hashlib.sha256(source_path.read_bytes()).hexdigest()

    retrieval_after_restart = RetrievalService(
        embedding=embedding,
        vector_store=ChromaVectorRepository(
            persist_dir=str(chroma_dir),
            collection_name="test_local_rag_chunks",
        ),
        lexical_store=SqliteFtsRepository(db_path=str(db_path)),
    )

    results = retrieval_after_restart.retrieve(
        query="persistencia chroma reinicio",
        candidate_k=5,
    )

    assert len(results) >= 1
    assert any(chunk.ref.document_id == expected_document_id for chunk in results)
