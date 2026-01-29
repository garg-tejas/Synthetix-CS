"""
Unified retriever interface for RAG pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .index import ChunkRecord


@dataclass
class RetrievalResult:
    """Result from a retrieval operation."""

    chunk: ChunkRecord
    score: float
    source: str


class Retriever(Protocol):
    """Protocol for retrieval implementations."""

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        """
        Search for chunks matching the query.

        Args:
            query: User query string
            top_k: Number of results to return

        Returns:
            List of RetrievalResult objects sorted by score (descending)
        """
        ...
