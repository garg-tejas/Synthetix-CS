"""
Context builder for RAG answer generation.

Formats retrieved chunks into LLM-ready text with citation markers [1], [2], ...
so the model can cite sources and we can map citations back to chunk IDs.
"""

from __future__ import annotations

from typing import List

from src.rag.retriever import RetrievalResult


def _approx_tokens(text: str) -> int:
    """Rough token count (~4 chars per token for English)."""
    return max(1, len(text) // 4)


def build_context(
    results: List[RetrievalResult],
    max_tokens: int = 2000,
) -> str:
    """
    Format retrieved chunks into a single context string with citation markers.

    Each chunk is prefixed with [1], [2], ... so the LLM can cite sources
    and we can map [n] back to chunk IDs.

    Args:
        results: Retrieval results (order preserved; index + 1 = citation number).
        max_tokens: Approximate token budget; chunks are truncated or dropped to fit.

    Returns:
        Single string like "[1] Chapter 1 > X: content... [2] Chapter 2 > Y: content..."
    """
    if not results:
        return ""

    parts: List[str] = []
    used = 0

    for i, r in enumerate(results, 1):
        chunk = r.chunk
        header = chunk.header_path or chunk.id
        text = (chunk.text or "").strip()
        segment = f"[{i}] {header}: {text}"
        seg_tokens = _approx_tokens(segment)

        if used + seg_tokens > max_tokens and parts:
            remaining = max_tokens - used - 80
            if remaining > 100 and text:
                segment = f"[{i}] {header}: {text[: remaining * 4]}..."
                parts.append(segment)
            break

        parts.append(segment)
        used += seg_tokens

    return "\n\n".join(parts)
