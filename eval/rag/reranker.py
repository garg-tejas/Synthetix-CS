from __future__ import annotations

"""
Cross-encoder reranker for second-stage re-ranking of retrieved chunks.

Uses sentence-transformers CrossEncoder under the hood so we don't have to
pull in raw transformers ourselves.
"""

from dataclasses import dataclass
from typing import Iterable, List, Tuple

from sentence_transformers import CrossEncoder

from .index import ChunkRecord


DEFAULT_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@dataclass
class CrossEncoderReranker:
    """
    Lightweight wrapper around a sentence-transformers CrossEncoder.

    Given a query and a list of (chunk, score) pairs, it re-scores them with
    the cross-encoder and returns a new list sorted by a weighted combination
    of the original score and the cross-encoder score.
    """

    model_name: str = DEFAULT_RERANKER_MODEL
    alpha: float = 0.5  # weight for original score vs cross-encoder score

    def __post_init__(self) -> None:
        self._model = CrossEncoder(self.model_name)

    def rerank(
        self,
        query: str,
        candidates: Iterable[Tuple[ChunkRecord, float]],
    ) -> List[Tuple[ChunkRecord, float]]:
        pairs: List[Tuple[ChunkRecord, float]] = list(candidates)
        if not pairs:
            return []

        # Build (query, document) pairs for cross-encoder
        texts = []
        for chunk, _orig_score in pairs:
            # Use header + leading text as the passage text.
            doc_text = f"{chunk.header_path}. {chunk.text[:512].replace('\n', ' ')}"
            texts.append((query, doc_text))

        ce_scores = self._model.predict(texts, batch_size=16)

        reranked: List[Tuple[ChunkRecord, float]] = []
        for (chunk, orig_score), ce_score in zip(pairs, ce_scores):
            combined = (1.0 - self.alpha) * orig_score + self.alpha * float(ce_score)
            reranked.append((chunk, combined))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked

