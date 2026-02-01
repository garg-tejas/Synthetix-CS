"""
Cross-encoder reranker for second-stage re-ranking of retrieved chunks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from sentence_transformers import CrossEncoder

from .index import ChunkRecord

DEFAULT_RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")


@dataclass
class CrossEncoderReranker:
    """Cross-encoder reranker for improving retrieval quality."""

    model_name: str = DEFAULT_RERANKER_MODEL
    alpha: float = 0.5

    def __post_init__(self) -> None:
        """Initialize the cross-encoder model."""
        self._model = CrossEncoder(self.model_name)

    def rerank(
        self,
        query: str,
        candidates: Iterable[Tuple[ChunkRecord, float]],
    ) -> List[Tuple[ChunkRecord, float]]:
        """
        Re-rank candidates using cross-encoder.

        Args:
            query: User query
            candidates: List of (chunk, score) pairs to re-rank

        Returns:
            Re-ranked list sorted by combined score.
        """
        pairs: List[Tuple[ChunkRecord, float]] = list(candidates)
        if not pairs:
            return []

        texts = []
        for chunk, _orig_score in pairs:
            doc_text = f"{chunk.header_path}. {chunk.text[:512].replace('\n', ' ')}"
            texts.append((query, doc_text))

        ce_scores = self._model.predict(texts, batch_size=16)

        reranked: List[Tuple[ChunkRecord, float]] = []
        for (chunk, orig_score), ce_score in zip(pairs, ce_scores):
            combined = (1.0 - self.alpha) * orig_score + self.alpha * float(ce_score)
            reranked.append((chunk, combined))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked
