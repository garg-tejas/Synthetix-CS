"""
Utility functions for RAG module.
"""

from __future__ import annotations

import re
from typing import Iterable

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to",
    "is", "are", "be", "as", "that", "this", "these", "those",
    "with", "by", "at", "from", "it", "its", "we", "they", "you",
}


def iter_tokens(text: str) -> Iterable[str]:
    """Extract tokens from text for BM25 indexing."""
    for match in TOKEN_RE.finditer(text.lower()):
        tok = match.group(0)
        if len(tok) <= 2:
            continue
        if tok in STOPWORDS:
            continue
        yield tok
