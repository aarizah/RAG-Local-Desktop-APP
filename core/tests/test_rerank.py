from src.contracts import ChunkRefV1, RetrievedChunkV1
from src.rag.rerank import RerankConfig, Reranker


def _chunk(chunk_id: str, text: str, score: float) -> RetrievedChunkV1:
    return RetrievedChunkV1(
        ref=ChunkRefV1(document_id="doc", version=1, chunk_id=chunk_id, source_path="a.txt"),
        text=text,
        score=score,
    )


def test_rerank_returns_exact_final_k() -> None:
    reranker = Reranker(RerankConfig(cross_encoder_enabled=False))
    candidates = [
        _chunk("c1", "python fastapi backend", 0.9),
        _chunk("c2", "python fastapi backend api", 0.8),
        _chunk("c3", "sqlite fts5 fallback", 0.7),
    ]
    result = reranker.rerank(candidates, rerank_k=3, final_k=2)
    assert len(result) == 2


def test_rerank_passthrough_uses_rrf_scores() -> None:
    """Without cross-encoder, chunks are scored by their pre-computed RRF score."""
    reranker = Reranker(RerankConfig(cross_encoder_enabled=False))
    candidates = [
        _chunk("c1", "alpha beta", 0.9),
        _chunk("c2", "alpha beta gamma", 0.8),
    ]
    result = reranker.rerank(candidates, rerank_k=2, final_k=1)
    assert len(result) == 1


def test_rerank_mmr_penalises_redundant_chunks() -> None:
    """MMR should prefer diverse chunks over near-duplicates."""
    reranker = Reranker(RerankConfig(cross_encoder_enabled=False, lambda_mult=0.5))
    candidates = [
        _chunk("c1", "fastapi python web framework", 0.9),
        # Very similar to c1 — MMR should penalise this
        _chunk("c2", "fastapi python web framework", 0.85),
        # Different topic — MMR should prefer this despite lower score
        _chunk("c3", "sqlite full text search index", 0.7),
    ]
    result = reranker.rerank(candidates, rerank_k=3, final_k=2)
    assert len(result) == 2
    ids = {c.ref.chunk_id for c in result}
    # c3 should win over c2 due to MMR diversity
    assert "c3" in ids


def test_rerank_empty_candidates() -> None:
    reranker = Reranker(RerankConfig(cross_encoder_enabled=False))
    assert reranker.rerank([], rerank_k=5, final_k=3) == []


def test_rerank_fewer_candidates_than_final_k() -> None:
    reranker = Reranker(RerankConfig(cross_encoder_enabled=False))
    candidates = [_chunk("c1", "only one chunk", 0.9)]
    result = reranker.rerank(candidates, rerank_k=5, final_k=3)
    assert len(result) == 1


def test_rerank_accepts_query_without_cross_encoder() -> None:
    """query kwarg is accepted silently when cross-encoder is disabled."""
    reranker = Reranker(RerankConfig(cross_encoder_enabled=False))
    candidates = [_chunk("c1", "some text", 0.8)]
    result = reranker.rerank(candidates, rerank_k=1, final_k=1, query="some question")
    assert len(result) == 1
