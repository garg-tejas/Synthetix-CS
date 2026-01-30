"""
Tests for RAG answer generation (context builder, citation extraction).
"""

from __future__ import annotations

import pytest

from src.generation import build_context, extract_citations
from src.rag import ChunkRecord, RetrievalResult


@pytest.fixture
def sample_results() -> list[RetrievalResult]:
    """Retrieval results for testing context and citations."""
    chunks = [
        ChunkRecord(
            id="chunk_001",
            book_id="book",
            header_path="Chapter 1 > Deadlock",
            chunk_type="definition",
            key_terms=[],
            text="A deadlock occurs when two or more processes wait for each other.",
        ),
        ChunkRecord(
            id="chunk_002",
            book_id="book",
            header_path="Chapter 2 > Scheduling",
            chunk_type="section",
            key_terms=[],
            text="The scheduler selects the next process to run on the CPU.",
        ),
    ]
    return [
        RetrievalResult(chunk=chunks[0], score=0.9, source="hybrid"),
        RetrievalResult(chunk=chunks[1], score=0.8, source="hybrid"),
    ]


def test_build_context_has_citation_markers(sample_results: list[RetrievalResult]):
    """Context string contains [1], [2] and chunk headers."""
    ctx = build_context(sample_results, max_tokens=500)
    assert "[1]" in ctx
    assert "[2]" in ctx
    assert "Chapter 1 > Deadlock" in ctx
    assert "Chapter 2 > Scheduling" in ctx
    assert "deadlock" in ctx.lower()
    assert "scheduler" in ctx.lower()


def test_build_context_empty_returns_empty():
    """Empty results yield empty context."""
    assert build_context([]) == ""


def test_build_context_respects_max_tokens(sample_results: list[RetrievalResult]):
    """Context is truncated when over token budget."""
    small = build_context(sample_results, max_tokens=50)
    full = build_context(sample_results, max_tokens=2000)
    assert len(small) <= len(full)


def test_extract_citations_parses_and_maps(sample_results: list[RetrievalResult]):
    """Extract [1] [2] from text and map to chunk IDs."""
    answer = "Deadlock is when processes wait [1]. The scheduler runs next [2]."
    citations = extract_citations(answer, sample_results)
    assert len(citations) == 2
    idx_to_id = {c.index: c.chunk_id for c in citations}
    assert idx_to_id[1] == "chunk_001"
    assert idx_to_id[2] == "chunk_002"


def test_extract_citations_empty_answer(sample_results: list[RetrievalResult]):
    """No citations in answer yields empty list."""
    assert extract_citations("No refs here.", sample_results) == []


def test_extract_citations_out_of_range_ignored(sample_results: list[RetrievalResult]):
    """[99] is ignored when only 2 results."""
    answer = "See [1] and [99]."
    citations = extract_citations(answer, sample_results)
    assert len(citations) == 1
    assert citations[0].index == 1
