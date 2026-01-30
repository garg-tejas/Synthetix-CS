"""
Answer generation module for RAG pipeline.

- Context building from retrieved chunks (citation markers [1], [2], ...)
- Answer generation with citations (Phase 2)
- Citation extraction and validation
"""

from .context_builder import build_context

__all__ = ["build_context"]
