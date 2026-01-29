"""
RAG (Retrieval-Augmented Generation) module.

Provides retrieval components for hybrid search over textbook chunks:
- BM25 sparse retrieval
- Dense semantic retrieval
- Hybrid search with RRF fusion
- Query rewriting and understanding
- Reranking
"""

from .bm25 import BM25Index
from .config import RAGConfig
from .dense import DenseIndex
from .hybrid import HybridSearcher
from .index import ChunkRecord, load_chunks
from .query_rewriter import QueryRewriter
from .query_understanding import QueryIntent, analyze
from .reranker import CrossEncoderReranker
from .retriever import RetrievalResult, Retriever

__all__ = [
    "ChunkRecord",
    "load_chunks",
    "BM25Index",
    "DenseIndex",
    "HybridSearcher",
    "RAGConfig",
    "QueryRewriter",
    "QueryIntent",
    "analyze",
    "CrossEncoderReranker",
    "RetrievalResult",
    "Retriever",
]
