"""
RAG agent: query analysis, retrieval, and answer generation (single-hop and multi-hop).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.generation import AnswerGenerator, Citation, GeneratedAnswer
from src.generation.context_builder import build_context
from src.rag.config import RAGConfig
from src.rag.retriever import Retriever, RetrievalResult

from .evaluator import AnswerEvaluator
from .memory import ConversationMemory
from .query_analyzer import QueryAnalyzer, QueryAnalysis


@dataclass
class AgentResponse:
    """Response from the RAG agent."""

    answer: str
    citations: List[Citation]
    sources_used: List[str]


def _merge_results(
    result_lists: List[List[RetrievalResult]],
    max_results: int,
) -> List[RetrievalResult]:
    """Dedupe by chunk.id (keep highest score), then take top max_results."""
    by_id: dict[str, RetrievalResult] = {}
    for results in result_lists:
        for r in results:
            cid = r.chunk.id
            if cid not in by_id or r.score > by_id[cid].score:
                by_id[cid] = r
    merged = sorted(by_id.values(), key=lambda x: -x.score)
    return merged[:max_results]


class RAGAgent:
    """RAG agent: single-hop or multi-hop retrieval, then generate answer."""

    def __init__(
        self,
        retriever: Retriever,
        generator: AnswerGenerator,
        query_analyzer: Optional[QueryAnalyzer] = None,
        rag_config: Optional[RAGConfig] = None,
        evaluator: Optional[AnswerEvaluator] = None,
        memory: Optional[ConversationMemory] = None,
        max_iterations: int = 2,
    ):
        self.retriever = retriever
        self.generator = generator
        self.query_analyzer = query_analyzer or QueryAnalyzer()
        self.rag_config = rag_config or RAGConfig()
        self.evaluator = evaluator
        self.memory = memory
        self.max_iterations = max(1, max_iterations)

    def answer(
        self,
        query: str,
        history: Optional[List[dict]] = None,
    ) -> AgentResponse:
        """Analyze query, retrieve (single or multi-hop), generate answer."""
        if history is None and self.memory is not None:
            history = self.memory.get_history()
        analysis = self.query_analyzer.analyze(query, history)
        if not analysis.requires_retrieval:
            fallback = AgentResponse(
                answer="I can only answer technical questions from the textbook. Ask about OS, DBMS, or computer networks.",
                citations=[],
                sources_used=[],
            )
            if self.memory is not None:
                self.memory.add_turn(query, fallback.answer, fallback.sources_used)
            return fallback
        top_k = self.rag_config.top_k
        if analysis.complexity == "multi-part" and len(analysis.sub_queries) >= 2:
            result_lists: List[List[RetrievalResult]] = []
            k_per = max(2, top_k // len(analysis.sub_queries))
            for sq in analysis.sub_queries:
                result_lists.append(self.retriever.search(sq, k_per))
            results = _merge_results(result_lists, top_k)
        else:
            results = self.retriever.search(query, top_k)
        if not results:
            no_result = AgentResponse(
                answer="No relevant passages were found. Try rephrasing your question.",
                citations=[],
                sources_used=[],
            )
            if self.memory is not None:
                self.memory.add_turn(query, no_result.answer, no_result.sources_used)
            return no_result
        resp: Optional[AgentResponse] = None
        for iteration in range(self.max_iterations):
            gen = self.generator.generate(query, results)
            resp = AgentResponse(
                answer=gen.answer,
                citations=gen.citations,
                sources_used=[r.chunk.id for r in results],
            )
            if self.evaluator is None:
                if self.memory is not None:
                    self.memory.add_turn(query, resp.answer, resp.sources_used)
                return resp
            context = build_context(results, max_tokens=2000)
            eval_result = self.evaluator.evaluate(query, gen.answer, context)
            if eval_result.is_complete or iteration == self.max_iterations - 1:
                if self.memory is not None:
                    self.memory.add_turn(query, resp.answer, resp.sources_used)
                return resp
            top_k = min(top_k + 5, self.rag_config.candidate_k)
            results = self.retriever.search(query, top_k)
            if not results:
                return resp
        if self.memory is not None:
            self.memory.add_turn(query, resp.answer, resp.sources_used)
        return resp
