from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from src.api import create_app
from src.contracts import ChunkRefV1, IngestRequestV1, QueryRequestV1
from src.rag.ingestion import IngestionService
from src.rag.rerank import RerankConfig, Reranker
from src.rag.retrieval import RetrievalService
from src.stores.lexical_store import SqliteFtsRepository
from src.stores.vector_store import VectorRecord
from tests.fakes.chunking import SimpleChunkingAdapter


@dataclass(slots=True)
class EvaluationReport:
    p50_total_ms: float
    p95_total_ms: float
    p50_retrieval_ms: float
    p95_retrieval_ms: float
    p50_rerank_ms: float
    p95_rerank_ms: float
    p50_generation_ms: float
    p95_generation_ms: float
    recall_at_5: float
    citation_coverage: float
    evaluated_queries: int


class FakeEmbedding:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class EmptyVectorStore:
    def upsert(self, records: list[VectorRecord]) -> None:
        return None

    def search(self, query_embedding: list[float], limit: int):
        return []


class TimedRetrievalService:
    def __init__(self, inner: RetrievalService):
        self.inner = inner
        self.latencies_ms: list[float] = []

    def retrieve(self, *, query: str, candidate_k: int):
        start = perf_counter()
        out = self.inner.retrieve(query=query, candidate_k=candidate_k)
        self.latencies_ms.append((perf_counter() - start) * 1000)
        return out


class TimedReranker:
    def __init__(self, inner: Reranker):
        self.inner = inner
        self.latencies_ms: list[float] = []

    def rerank(self, candidates, rerank_k: int, final_k: int):
        start = perf_counter()
        out = self.inner.rerank(candidates, rerank_k, final_k)
        self.latencies_ms.append((perf_counter() - start) * 1000)
        return out


class TimedGeneration:
    def __init__(self):
        self.latencies_ms: list[float] = []

    def generate(self, *, question: str, contexts: list[tuple[ChunkRefV1, str]], correlation_id: str) -> str:
        start = perf_counter()
        citation = contexts[0][0].citation if contexts else "none"
        answer = f"respuesta basada en evidencia [{citation}]"
        self.latencies_ms.append((perf_counter() - start) * 1000)
        return answer


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil((percentile / 100) * len(ordered)) - 1)
    return round(ordered[index], 3)


def _load_golden_set(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        rows.append(json.loads(line))
    return rows


def run_e2e_evaluation(*, golden_set_path: Path, workdir: Path) -> EvaluationReport:
    rows = _load_golden_set(golden_set_path)

    db_path = workdir / "e2e_eval.db"
    docs_dir = workdir / "s3"
    docs_dir.mkdir(parents=True, exist_ok=True)

    embedding = FakeEmbedding()
    vector_store = EmptyVectorStore()
    lexical = SqliteFtsRepository(db_path=str(db_path))
    ingestion = IngestionService(
        sqlite_path=str(db_path),
        chunker=SimpleChunkingAdapter(max_chars=500, overlap=0),
        embedding=embedding,
        vector_store=vector_store,
        lexical_store=lexical,
        s3_dir=str(docs_dir),
    )

    for row in rows:
        doc_path = docs_dir / f"{row['document_id']}.pdf"
        doc_path.write_text(row["content"], encoding="utf-8")
        ingestion.ingest(IngestRequestV1(source_path=doc_path.name))

    retrieval = TimedRetrievalService(
        RetrievalService(embedding=embedding, vector_store=vector_store, lexical_store=lexical)
    )
    reranker = TimedReranker(Reranker(RerankConfig()))
    generation = TimedGeneration()

    app = create_app(
        ingestion_service=ingestion,
        retrieval_service=retrieval,
        reranker=reranker,
        generation_service=generation,
    )
    client = TestClient(app)

    total_ms: list[float] = []
    hits = 0
    with_citation = 0

    for row in rows:
        payload = QueryRequestV1(query=row["query"]).model_dump()
        response = client.post("/v1/query", json=payload)
        assert response.status_code == 200
        body = response.json()
        total_ms.append(float(body["total_ms"]))
        citations = body.get("citations", [])
        if citations:
            with_citation += 1
        if row["expected_citation"] in citations[:5]:
            hits += 1

    evaluated = len(rows)
    return EvaluationReport(
        p50_total_ms=_percentile(total_ms, 50),
        p95_total_ms=_percentile(total_ms, 95),
        p50_retrieval_ms=_percentile(retrieval.latencies_ms, 50),
        p95_retrieval_ms=_percentile(retrieval.latencies_ms, 95),
        p50_rerank_ms=_percentile(reranker.latencies_ms, 50),
        p95_rerank_ms=_percentile(reranker.latencies_ms, 95),
        p50_generation_ms=_percentile(generation.latencies_ms, 50),
        p95_generation_ms=_percentile(generation.latencies_ms, 95),
        recall_at_5=round(hits / evaluated, 3),
        citation_coverage=round(with_citation / evaluated, 3),
        evaluated_queries=evaluated,
    )
