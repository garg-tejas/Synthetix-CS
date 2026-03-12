"""
Context builder for RAG answer generation.

Formats retrieved chunks into LLM-ready text with citation markers [1], [2], ...
so the model can cite sources and we can map citations back to chunk IDs.
"""

from __future__ import annotations

from typing import List, Tuple

from src.rag.retriever import RetrievalResult


def _approx_tokens(text: str) -> int:
    """Rough token count (~4 chars per token for English)."""
    return max(1, len(text) // 4)


def _reorder_lost_in_middle(
    items: List[Tuple[int, str]],
) -> List[Tuple[int, str]]:
    """
    Reorder so the most relevant items land at the start and end of the
    context window, pushing least-relevant items to the middle.

    Uses the strategy from 'Lost in the Middle' (Liu et al., 2023):
    keep first half in order, reverse second half so next-best items
    appear at the tail.

    Each item is ``(citation_index, formatted_segment)``.
    Input is assumed to be in descending relevance order.
    """
    if len(items) <= 2:
        return items
    mid = (len(items) + 1) // 2
    first_half = items[:mid]
    second_half = items[mid:][::-1]
    return first_half + second_half


def build_context(
    results: List[RetrievalResult],
    max_tokens: int = 2000,
) -> str:
    """
    Format retrieved chunks into a single context string with citation markers.

    Each chunk is prefixed with [1], [2], ... so the LLM can cite sources
    and we can map [n] back to chunk IDs.

    Chunks are reordered using the lost-in-the-middle strategy so that the
    most relevant chunks appear at the start and end of the context window.

    Args:
        results: Retrieval results in descending relevance order.
        max_tokens: Approximate token budget; chunks are truncated or dropped to fit.

    Returns:
        Single string like "[1] Chapter 1 > X: content... [3] Chapter 3 > Z: content..."
    """
    if not results:
        return ""

    # Phase 1: Select chunks that fit within token budget.
    # Each entry is (citation_index, formatted_segment_string).
    selected: List[Tuple[int, str]] = []
    used = 0

    for i, r in enumerate(results, 1):
        chunk = r.chunk
        header = chunk.header_path or chunk.id
        text = (chunk.text or "").strip()
        segment = f"[{i}] {header}: {text}"
        seg_tokens = _approx_tokens(segment)

        if used + seg_tokens > max_tokens and selected:
            remaining = max_tokens - used - 80
            if remaining > 100 and text:
                truncated = f"[{i}] {header}: {text[: remaining * 4]}..."
                selected.append((i, truncated))
            break

        selected.append((i, segment))
        used += seg_tokens

    # Phase 2: Reorder for lost-in-the-middle mitigation.
    reordered = _reorder_lost_in_middle(selected)

    # Phase 3: Build final context string.
    return "\n\n".join(seg for _, seg in reordered)
