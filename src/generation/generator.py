"""
Answer generator: builds context, calls LLM, returns answer text.
Citations are populated separately by citation extraction (see citations.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Optional

from src.llm.client import ModelScopeClient
from src.rag.retriever import RetrievalResult

from .citations import Citation, extract_citations
from .config import GenerationConfig
from .context_builder import build_context
from .prompts import ANSWER_PROMPT


@dataclass
class GeneratedAnswer:
    """Result of RAG answer generation."""

    answer: str
    citations: List[Citation]
    confidence: float = 0.0


class AnswerGenerator:
    """Generate answers from a query and retrieved chunks using the LLM."""

    def __init__(self, client: ModelScopeClient):
        self.client = client

    def generate(
        self,
        query: str,
        results: List[RetrievalResult],
        config: Optional[GenerationConfig] = None,
    ) -> GeneratedAnswer:
        """Build context from results, call LLM, return answer. Citations left for extractor."""
        config = config or GenerationConfig()
        context = build_context(results, max_tokens=config.context_max_tokens)
        prompt = ANSWER_PROMPT.format(context=context, query=query)
        answer_text = self.client.generate_single(
            prompt,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        answer_str = answer_text or ""
        citations = extract_citations(answer_str, results)
        return GeneratedAnswer(
            answer=answer_str,
            citations=citations,
            confidence=0.0,
        )

    def generate_stream(
        self,
        query: str,
        results: List[RetrievalResult],
        config: Optional[GenerationConfig] = None,
    ) -> Iterator[str]:
        """Yield token chunks from the LLM. Caller accumulates and runs extract_citations when done."""
        config = config or GenerationConfig()
        context = build_context(results, max_tokens=config.context_max_tokens)
        prompt = ANSWER_PROMPT.format(context=context, query=query)
        for chunk in self.client.stream(
            prompt,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        ):
            if chunk:
                yield chunk
