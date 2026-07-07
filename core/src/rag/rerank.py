from __future__ import annotations

import math
from dataclasses import dataclass

from src.contracts import RetrievedChunkV1


@dataclass(slots=True)
class RerankConfig:
    strategy: str = "cross_encoder"
    lambda_mult: float = 0.5
    cross_encoder_enabled: bool = False
    cross_encoder_model_id: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class Reranker:
    """Two-phase reranker.

    Phase 1 — Scoring:
      • Cross-encoder (if enabled and query is provided): scores each (query, chunk) pair
        with a bi-encoder-free model; raw logits are mapped to [0, 1] via sigmoid.
      • Passthrough (fallback): uses the pre-computed RRF scores from RetrievalService.

    Phase 2 — Selection:
      • MMR (Maximal Marginal Relevance): balances relevance vs. redundancy to pick
        a diverse final_k from the top rerank_k candidates.
    """

    def __init__(self, config: RerankConfig):
        self.config = config
        self._cross_encoder = None
        if config.cross_encoder_enabled:
            self._load_cross_encoder()

    def _load_cross_encoder(self) -> None:
        try:
            from sentence_transformers import CrossEncoder  # noqa: PLC0415

            self._cross_encoder = CrossEncoder(self.config.cross_encoder_model_id)
        except ImportError:  # pragma: no cover
            self._cross_encoder = None

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def _token_set(text: str) -> set[str]:
        return {token.strip(".,;:!?\"'()[]{}") for token in text.lower().split() if token}

    def _redundancy(self, candidate: RetrievedChunkV1, selected: list[RetrievedChunkV1]) -> float:
        if not selected:
            return 0.0
        cand_tokens = self._token_set(candidate.text)
        if not cand_tokens:
            return 0.0
        max_sim = 0.0
        for item in selected:
            item_tokens = self._token_set(item.text)
            union = cand_tokens | item_tokens
            if not union:
                continue
            inter = cand_tokens & item_tokens
            max_sim = max(max_sim, len(inter) / len(union))
        return max_sim

    def rerank(
        self,
        candidates: list[RetrievedChunkV1],
        rerank_k: int,
        final_k: int,
        *,
        query: str = "",
    ) -> list[RetrievedChunkV1]:
        if not candidates:
            return []

        top = candidates[:rerank_k]

        if self._cross_encoder is not None and query:
            pairs = [(query, chunk.text) for chunk in top]
            raw_scores = self._cross_encoder.predict(pairs)
            scored = [
                (chunk, self._sigmoid(float(s)))
                for chunk, s in zip(top, raw_scores, strict=False)
            ]
        else:
            # Use RRF scores already fused by RetrievalService
            scored = [(chunk, chunk.score) for chunk in top]

        scored.sort(key=lambda pair: pair[1], reverse=True)

        selected: list[RetrievedChunkV1] = []
        while scored and len(selected) < final_k:
            best_idx = 0
            best_value = float("-inf")
            for idx, (chunk, score) in enumerate(scored):
                mmr_value = self.config.lambda_mult * score - (
                    1.0 - self.config.lambda_mult
                ) * self._redundancy(chunk, selected)
                if mmr_value > best_value:
                    best_value = mmr_value
                    best_idx = idx
            selected.append(scored.pop(best_idx)[0])

        return selected
