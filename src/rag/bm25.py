"""
BM25 sparse retriever over textbook chunks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from rank_bm25 import BM25Okapi

from .index import ChunkRecord
from .utils import iter_tokens


@dataclass
class BM25Index:
    """BM25 sparse retrieval index."""

    bm25: BM25Okapi
    chunks: List[ChunkRecord]

    @classmethod
    def from_chunks(cls, chunks: List[ChunkRecord]) -> "BM25Index":
        """Build BM25 index from chunks."""
        tokenized_docs = [list(iter_tokens(c.text)) for c in chunks]
        bm25 = BM25Okapi(tokenized_docs)
        return cls(bm25=bm25, chunks=chunks)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[ChunkRecord, float]]:
        """Search for top-k chunks matching the query."""
        query_tokens = list(iter_tokens(query))
        scores = self.bm25.get_scores(query_tokens)
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        results: List[Tuple[ChunkRecord, float]] = []
        for idx, score in indexed_scores[:top_k]:
            if score <= 0:
                continue
            results.append((self.chunks[idx], float(score)))
        return results
