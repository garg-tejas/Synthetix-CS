"""
Tests for RAG retrieval pipeline.
"""

from __future__ import annotations

import pytest

from src.rag import (
    BM25Index,
    ChunkRecord,
    DenseIndex,
    HybridSearcher,
    RAGConfig,
    RetrievalResult,
    load_chunks,
)


@pytest.fixture
def sample_chunks() -> list[ChunkRecord]:
    """Create sample chunks for testing."""
    return [
        ChunkRecord(
            id="test_001",
            book_id="test_book",
            header_path="Chapter 1 > Deadlock",
            chunk_type="definition",
            key_terms=["deadlock", "circular", "wait"],
            text="A deadlock is a situation where two or more processes are blocked, each waiting for a resource held by another.",
            potential_questions=[],
        ),
        ChunkRecord(
            id="test_002",
            book_id="test_book",
            header_path="Chapter 1 > Process Scheduling",
            chunk_type="section",
            key_terms=["scheduling", "cpu", "process"],
            text="Process scheduling is the mechanism by which the operating system selects which process to run next on the CPU.",
            potential_questions=[],
        ),
        ChunkRecord(
            id="test_003",
            book_id="test_book",
            header_path="Chapter 2 > TCP Handshake",
            chunk_type="protocol",
            key_terms=["tcp", "handshake", "connection"],
            text="The TCP three-way handshake establishes a connection between client and server using SYN and ACK packets.",
            potential_questions=[],
        ),
    ]


def test_bm25_index_search(sample_chunks: list[ChunkRecord]):
    """Test BM25 index search."""
    index = BM25Index.from_chunks(sample_chunks)
    results = index.search("deadlock", top_k=2)
    
    assert len(results) > 0
    assert results[0][0].id == "test_001"
    assert results[0][1] > 0


def test_dense_index_search(sample_chunks: list[ChunkRecord]):
    """Test dense index search."""
    index = DenseIndex.from_chunks(sample_chunks)
    results = index.search("what is a deadlock", top_k=2)
    
    assert len(results) > 0
    assert results[0][1] > 0


def test_hybrid_searcher_search(sample_chunks: list[ChunkRecord]):
    """Test HybridSearcher search returns RetrievalResult."""
    searcher = HybridSearcher.from_chunks(
        sample_chunks,
        use_reranker=False,
        use_hyde=False,
    )
    results = searcher.search("deadlock", top_k=2)
    
    assert len(results) > 0
    assert isinstance(results[0], RetrievalResult)
    assert results[0].chunk.id == "test_001"
    assert results[0].score > 0
    assert results[0].source in ("hybrid", "reranked")


def test_hybrid_searcher_with_config(sample_chunks: list[ChunkRecord]):
    """Test HybridSearcher with custom RAGConfig."""
    config = RAGConfig(
        use_hyde=False,
        use_reranker=False,
        use_query_rewriting=True,
        top_k=3,
        candidate_k=10,
    )
    searcher = HybridSearcher.from_chunks(sample_chunks, config=config)
    results = searcher.search("deadlock")
    
    assert len(results) <= config.top_k
    assert all(isinstance(r, RetrievalResult) for r in results)


def test_hybrid_searcher_search_raw(sample_chunks: list[ChunkRecord]):
    """Test HybridSearcher search_raw for backward compatibility."""
    searcher = HybridSearcher.from_chunks(
        sample_chunks,
        use_reranker=False,
        use_hyde=False,
    )
    results = searcher.search_raw("deadlock", top_k=2)
    
    assert len(results) > 0
    assert isinstance(results[0], tuple)
    assert len(results[0]) == 2
    assert isinstance(results[0][0], ChunkRecord)
    assert isinstance(results[0][1], float)


def test_retrieval_result():
    """Test RetrievalResult dataclass."""
    chunk = ChunkRecord(
        id="test",
        book_id="book",
        header_path="Header",
        chunk_type="section",
        key_terms=[],
        text="Test text",
    )
    result = RetrievalResult(chunk=chunk, score=0.95, source="hybrid")
    
    assert result.chunk.id == "test"
    assert result.score == 0.95
    assert result.source == "hybrid"


@pytest.mark.skipif(
    True,
    reason="chunks.jsonl integration test - enable when data is available",
)
def test_integration_with_real_data():
    """Integration test with real chunks.jsonl if available."""
    try:
        chunks = load_chunks()
    except FileNotFoundError:
        pytest.skip("chunks.jsonl not found")
    
    if len(chunks) == 0:
        pytest.skip("No chunks loaded")
    
    searcher = HybridSearcher.from_chunks(
        chunks[:100],
        use_reranker=False,
        use_hyde=False,
    )
    results = searcher.search("what is a deadlock", top_k=5)
    
    assert len(results) > 0
    assert all(isinstance(r, RetrievalResult) for r in results)
    assert all(r.score > 0 for r in results)
