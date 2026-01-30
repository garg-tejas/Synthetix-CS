"""
Answer generation module for RAG pipeline.

- Context building from retrieved chunks (citation markers [1], [2], ...)
- Answer generation with citations
- Citation extraction from model output
"""

from .citations import Citation, extract_citations
from .config import GenerationConfig
from .context_builder import build_context
from .generator import AnswerGenerator, GeneratedAnswer
from .prompts import ANSWER_PROMPT

__all__ = [
    "build_context",
    "Citation",
    "extract_citations",
    "GenerationConfig",
    "ANSWER_PROMPT",
    "AnswerGenerator",
    "GeneratedAnswer",
]
