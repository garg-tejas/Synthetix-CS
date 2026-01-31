"""
Tests for orchestrator: query analyzer, RAG agent (single-hop), conversation memory.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.generation import AnswerGenerator, Citation, GeneratedAnswer
from src.rag import ChunkRecord, RetrievalResult

from src.orchestrator import (
    AgentResponse,
    AnswerEvaluator,
    ConversationMemory,
    EvalResult,
    QueryAnalysis,
    QueryAnalyzer,
    RAGAgent,
    Turn,
)


# --- Query analyzer ---


def test_query_analyzer_output_shape():
    """QueryAnalyzer.analyze returns QueryAnalysis with intent, complexity, sub_queries, entities, requires_retrieval."""
    analyzer = QueryAnalyzer()
    result = analyzer.analyze("What is deadlock?")
    assert isinstance(result, QueryAnalysis)
    assert hasattr(result, "intent")
    assert hasattr(result, "complexity")
    assert hasattr(result, "sub_queries")
    assert hasattr(result, "entities")
    assert hasattr(result, "requires_retrieval")
    assert isinstance(result.intent, str)
    assert isinstance(result.complexity, str)
    assert isinstance(result.sub_queries, list)
    assert isinstance(result.entities, list)
    assert isinstance(result.requires_retrieval, bool)


def test_query_analyzer_greeting_no_retrieval():
    """Greetings like 'hello' yield requires_retrieval=False."""
    analyzer = QueryAnalyzer()
    for q in ("hi", "hello!", "thanks", "bye"):
        r = analyzer.analyze(q)
        assert r.requires_retrieval is False
        assert r.complexity == "simple"


def test_query_analyzer_technical_requires_retrieval():
    """Technical questions yield requires_retrieval=True."""
    analyzer = QueryAnalyzer()
    r = analyzer.analyze("What is deadlock in operating systems?")
    assert r.requires_retrieval is True
    assert r.sub_queries  # at least the full query
    assert r.intent in ("definition", "factual", "procedural", "comparison")


def test_query_analyzer_multi_part_decomposes():
    """Multi-part query yields complexity 'multi-part' and multiple sub_queries."""
    analyzer = QueryAnalyzer()
    r = analyzer.analyze("What is deadlock and how to prevent it?")
    assert r.complexity == "multi-part"
    assert len(r.sub_queries) >= 2


def test_query_analyzer_empty_query():
    """Empty or whitespace query yields requires_retrieval=False."""
    analyzer = QueryAnalyzer()
    assert analyzer.analyze("").requires_retrieval is False
    assert analyzer.analyze("   ").requires_retrieval is False


def test_query_analyzer_accepts_history():
    """analyze() accepts optional history (reserved for follow-up)."""
    analyzer = QueryAnalyzer()
    r = analyzer.analyze("What is a semaphore?", history=[{"query": "Hi", "answer": "Hello!"}])
    assert r.requires_retrieval is True


# --- Conversation memory ---


def test_memory_add_turn_get_history():
    """add_turn stores turn; get_history returns last N as list of dicts."""
    mem = ConversationMemory(max_turns=5)
    assert mem.get_history() == []
    mem.add_turn("What is deadlock?", "Deadlock is when processes wait for each other.", ["c1"])
    mem.add_turn("How to prevent it?", "Use ordering or timeouts.", ["c2"])
    hist = mem.get_history(last_n=2)
    assert len(hist) == 2
    assert hist[0]["query"] == "What is deadlock?"
    assert hist[0]["answer"] == "Deadlock is when processes wait for each other."
    assert hist[1]["query"] == "How to prevent it?"


def test_memory_get_relevant_context():
    """get_relevant_context returns last N turns as Q/A string."""
    mem = ConversationMemory(max_turns=5)
    mem.add_turn("Q1", "A1", [])
    mem.add_turn("Q2", "A2", [])
    ctx = mem.get_relevant_context("anything", last_n=2)
    assert "Q: Q1" in ctx
    assert "A: A1" in ctx
    assert "Q: Q2" in ctx
    assert "A: A2" in ctx


def test_memory_clear():
    """clear() removes all turns."""
    mem = ConversationMemory(max_turns=5)
    mem.add_turn("Q", "A", [])
    mem.clear()
    assert mem.get_history() == []
    assert mem.get_relevant_context("q") == ""


def test_memory_max_turns_trimmed():
    """When over max_turns, only last max_turns are kept."""
    mem = ConversationMemory(max_turns=2)
    mem.add_turn("Q1", "A1", [])
    mem.add_turn("Q2", "A2", [])
    mem.add_turn("Q3", "A3", [])
    hist = mem.get_history(last_n=10)
    assert len(hist) == 2
    assert hist[0]["query"] == "Q2"
    assert hist[1]["query"] == "Q3"


def test_turn_dataclass():
    """Turn has query, answer, citation_chunk_ids."""
    t = Turn(query="q", answer="a", citation_chunk_ids=["id1"])
    assert t.query == "q"
    assert t.answer == "a"
    assert t.citation_chunk_ids == ["id1"]


# --- Answer evaluator ---


def test_evaluator_output_shape():
    """AnswerEvaluator.evaluate returns EvalResult with is_complete, missing_aspects, confidence."""
    ev = AnswerEvaluator()
    r = ev.evaluate("What is X?", "This is a sufficiently long answer with [1] citation.", "Some context.")
    assert isinstance(r, EvalResult)
    assert hasattr(r, "is_complete")
    assert hasattr(r, "missing_aspects")
    assert hasattr(r, "confidence")
    assert isinstance(r.missing_aspects, list)
    assert 0 <= r.confidence <= 1.0


def test_evaluator_short_answer_incomplete():
    """Short answer without citations is incomplete."""
    ev = AnswerEvaluator()
    r = ev.evaluate("q", "Short.", "context")
    assert r.is_complete is False
    assert "answer_too_short" in r.missing_aspects or "no_citations" in r.missing_aspects


# --- RAG agent (single-hop with mocks) ---


def _make_chunk(cid: str, text: str = "Sample text.") -> ChunkRecord:
    return ChunkRecord(
        id=cid,
        book_id="book",
        header_path="Chapter 1",
        chunk_type="section",
        key_terms=[],
        text=text,
    )


@pytest.fixture
def mock_retriever():
    """Retriever that returns a fixed list of RetrievalResult."""
    chunk = _make_chunk("chunk_1", "Deadlock is when two processes wait for each other.")
    results = [RetrievalResult(chunk=chunk, score=0.9, source="hybrid")]

    ret = MagicMock()
    ret.search = MagicMock(return_value=results)
    return ret


@pytest.fixture
def mock_generator():
    """AnswerGenerator that returns a fixed GeneratedAnswer."""
    gen = MagicMock(spec=AnswerGenerator)
    gen.generate = MagicMock(
        return_value=GeneratedAnswer(
            answer="A deadlock occurs when two or more processes block each other [1].",
            citations=[Citation(index=1, chunk_id="chunk_1", snippet="Deadlock is when...")],
            confidence=0.8,
        )
    )
    return gen


def test_agent_single_hop_returns_answer_and_citations(mock_retriever, mock_generator):
    """RAGAgent.answer() returns AgentResponse with answer, citations, sources_used."""
    agent = RAGAgent(retriever=mock_retriever, generator=mock_generator)
    resp = agent.answer("What is deadlock?")
    assert isinstance(resp, AgentResponse)
    assert resp.answer
    assert isinstance(resp.citations, list)
    assert isinstance(resp.sources_used, list)
    assert "chunk_1" in resp.sources_used
    mock_retriever.search.assert_called_once()
    mock_generator.generate.assert_called_once()


def test_agent_greeting_returns_fallback_no_retrieval(mock_retriever, mock_generator):
    """For greetings, agent returns fallback message and does not call retriever."""
    agent = RAGAgent(retriever=mock_retriever, generator=mock_generator)
    resp = agent.answer("hello")
    assert "technical questions" in resp.answer.lower()
    assert resp.citations == []
    assert resp.sources_used == []
    mock_retriever.search.assert_not_called()
    mock_generator.generate.assert_not_called()


def test_agent_no_results_returns_message(mock_generator):
    """When retriever returns empty, agent returns no-results message."""
    empty_ret = MagicMock()
    empty_ret.search = MagicMock(return_value=[])
    agent = RAGAgent(retriever=empty_ret, generator=mock_generator)
    resp = agent.answer("obscure query xyz")
    assert "relevant passages" in resp.answer.lower() or "rephrasing" in resp.answer.lower()
    assert resp.citations == []
    assert resp.sources_used == []
    mock_generator.generate.assert_not_called()


def test_agent_with_memory_stores_turn(mock_retriever, mock_generator):
    """When memory is provided, agent adds turn after answering."""
    mem = ConversationMemory(max_turns=5)
    agent = RAGAgent(retriever=mock_retriever, generator=mock_generator, memory=mem)
    resp = agent.answer("What is deadlock?")
    hist = mem.get_history()
    assert len(hist) == 1
    assert hist[0]["query"] == "What is deadlock?"
    assert hist[0]["answer"] == resp.answer
