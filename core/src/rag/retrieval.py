from __future__ import annotations

from src.contracts import RetrievedChunkV1
from src.rag.embedding import EmbeddingPort
from src.stores.lexical_store import SqliteFtsRepository
from src.stores.vector_store import VectorStorePort


class RetrievalService:
    def __init__(
        self,
        *,
        embedding: EmbeddingPort,
        vector_store: VectorStorePort,
        lexical_store: SqliteFtsRepository,
        semantic_threshold: float = 0.0,
        rrf_k: int = 60,
    ):
        self.embedding = embedding
        self.vector_store = vector_store
        self.lexical_store = lexical_store
        self.semantic_threshold = semantic_threshold
        self.rrf_k = rrf_k

    def retrieve(self, *, query: str, candidate_k: int) -> list[RetrievedChunkV1]:
        qvec = self.embedding.embed_query(query)

        # Always query both stores up to candidate_k each
        semantic = self.vector_store.search(qvec, limit=candidate_k)
        lexical = self.lexical_store.search(query, limit=candidate_k)

        # Drop semantic results below the quality threshold
        if self.semantic_threshold > 0.0:
            semantic = [c for c in semantic if c.score >= self.semantic_threshold]

        # Build rank-by-source lookups: uid → 0-based rank
        def uid(c: RetrievedChunkV1) -> str:
            return f"{c.ref.document_id}:{c.ref.chunk_id}"

        sem_rank: dict[str, int] = {uid(c): rank for rank, c in enumerate(semantic)}
        lex_rank: dict[str, int] = {uid(c): rank for rank, c in enumerate(lexical)}

        # Deduplicate, preserving semantic score for chunks that appear in both
        chunks_by_uid: dict[str, RetrievedChunkV1] = {}
        for c in semantic:
            chunks_by_uid[uid(c)] = c
        for c in lexical:
            k = uid(c)
            if k not in chunks_by_uid:
                chunks_by_uid[k] = c

        # RRF fusion: chunks in both sources rank higher than chunks in either alone
        # Absent chunks receive a penalty rank beyond the search window
        miss_rank = candidate_k + 1
        k = self.rrf_k

        def rrf_score(u: str) -> float:
            return 1.0 / (k + sem_rank.get(u, miss_rank)) + 1.0 / (k + lex_rank.get(u, miss_rank))

        ranked_uids = sorted(chunks_by_uid, key=rrf_score, reverse=True)
        return [chunks_by_uid[u] for u in ranked_uids[:candidate_k]]
