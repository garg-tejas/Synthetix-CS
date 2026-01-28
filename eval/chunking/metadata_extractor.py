"""
Minimal key-term extractor for chunks.

This is intentionally simple (no external NLP deps yet):
- Lowercase
- Split on non-alphanumeric boundaries
- Remove short tokens and a small stopword list
- Return top-N most frequent tokens as `key_terms`
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, List


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

# Very small stopword list; can be extended later.
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "in",
    "on",
    "for",
    "to",
    "is",
    "are",
    "be",
    "as",
    "that",
    "this",
    "these",
    "those",
    "with",
    "by",
    "at",
    "from",
    "it",
    "its",
    "we",
    "they",
    "you",
}


def iter_tokens(text: str) -> Iterable[str]:
    for match in TOKEN_RE.finditer(text.lower()):
        tok = match.group(0)
        if len(tok) <= 2:
            continue
        if tok in STOPWORDS:
            continue
        yield tok


def extract_key_terms(text: str, max_terms: int = 8) -> List[str]:
    counts = Counter(iter_tokens(text))
    if not counts:
        return []
    # Most common tokens; preserve deterministic ordering
    return [tok for tok, _ in counts.most_common(max_terms)]


if __name__ == "__main__":
    sample = "The LRU (Least Recently Used) page replacement algorithm uses temporal locality."
    print(extract_key_terms(sample))

