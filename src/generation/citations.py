"""
Extract [1], [2], ... references from generated text and map to chunk IDs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from src.rag.retriever import RetrievalResult


@dataclass
class Citation:
    """A single citation mapping [n] to a chunk."""

    index: int
    chunk_id: str
    snippet: str = ""


def extract_citations(
    answer: str,
    results: List[RetrievalResult],
) -> List[Citation]:
    """
    Parse [n] references in answer and map to chunk IDs from results.
    results[0] -> [1], results[1] -> [2], etc.
    """
    if not results:
        return []
    indices = set()
    for m in re.finditer(r"\[(\d+)\]", answer):
        try:
            n = int(m.group(1))
            if 1 <= n <= len(results):
                indices.add(n)
        except ValueError:
            continue
    citations: List[Citation] = []
    for n in sorted(indices):
        r = results[n - 1]
        chunk = r.chunk
        snippet = (chunk.text or "")[:200].strip()
        if len((chunk.text or "")) > 200:
            snippet += "..."
        citations.append(Citation(index=n, chunk_id=chunk.id, snippet=snippet))
    return citations
