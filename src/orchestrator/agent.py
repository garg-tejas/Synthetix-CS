"""
RAG agent: query analysis, retrieval, and answer generation (single-hop).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.generation import AnswerGenerator, Citation, GeneratedAnswer
from src.rag.config import RAGConfig
from src.rag.retriever import Retriever, RetrievalResult

from .query_analyzer import QueryAnalyzer, QueryAnalysis


@dataclass
class AgentResponse:
    """Response from the RAG agent."""

    answer: str
    citations: List[Citation]
    sources_used: List[str]


class RAGAgent:
    """Single-hop RAG: analyze query, retrieve, generate answer."""

    def __init__(
        self,
        retriever: Retriever,
        generator: AnswerGenerator,
        query_analyzer: Optional[QueryAnalyzer] = None,
        rag_config: Optional[RAGConfig] = None,
    ):
        self.retriever = retriever
        self.generator = generator
        self.query_analyzer = query_analyzer or QueryAnalyzer()
        self.rag_config = rag_config or RAGConfig()

    def answer(
        self,
        query: str,
        history: Optional[List[dict]] = None,
    ) -> AgentResponse:
        """Analyze query, retrieve chunks, generate answer. Single-hop only."""
        analysis = self.query_analyzer.analyze(query, history)
        if not analysis.requires_retrieval:
            return AgentResponse(
                answer="I can only answer technical questions from the textbook. Ask about OS, DBMS, or computer networks.",
                citations=[],
                sources_used=[],
            )
        top_k = self.rag_config.top_k
        results: List[RetrievalResult] = self.retriever.search(query, top_k)
        if not results:
            return AgentResponse(
                answer="No relevant passages were found. Try rephrasing your question.",
                citations=[],
                sources_used=[],
            )
        gen: GeneratedAnswer = self.generator.generate(query, results)
        sources = [r.chunk.id for r in results]
        return AgentResponse(
            answer=gen.answer,
            citations=gen.citations,
            sources_used=sources,
        )
