"""
Configuration for RAG retrieval pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RAGConfig:
    """Configuration for RAG retrieval."""

    use_hyde: bool = True
    use_reranker: bool = True
    use_query_rewriting: bool = True
    bm25_weight: float = 0.5
    dense_weight: float = 0.5
    top_k: int = 5
    candidate_k: int = 20
