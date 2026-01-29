"""
Query understanding for retrieval bias and intent detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from .index import ChunkRecord


@dataclass
class QueryIntent:
    """Result of query analysis."""

    is_definition_seeking: bool
    concept: str | None
    negative_signals: List[str] = field(default_factory=list)
    is_procedural: bool = False
    is_comparative: bool = False


_DEFINITION_PATTERNS: List[Tuple[re.Pattern[str], int]] = [
    (re.compile(r"\bwhat\s+is\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bdefine\s+(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bexplain\s+(?:what\s+is\s+)?(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bmeaning\s+of\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bdescribe\s+(?:what\s+is\s+)?(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"(.+?)\s+definition\s*$", re.I), 1),
]


def analyze(query: str) -> QueryIntent:
    """Analyze query for intent and extract concept if definition-seeking."""
    q = query.strip()
    q_lower = q.lower()
    concept: str | None = None

    is_procedural = _is_procedural_query(q_lower)
    is_comparative = _is_comparative_query(q_lower)

    for pat, grp in _DEFINITION_PATTERNS:
        m = pat.search(q)
        if m:
            raw = m.group(grp).strip()
            if raw:
                concept = raw.rstrip("?").strip()
            negative = _negative_signals_for_query(concept, q_lower)
            return QueryIntent(
                is_definition_seeking=True,
                concept=concept or None,
                negative_signals=negative,
                is_procedural=is_procedural,
                is_comparative=is_comparative,
            )

    negative = _negative_signals_for_query(None, q_lower)
    return QueryIntent(
        is_definition_seeking=False,
        concept=None,
        negative_signals=negative,
        is_procedural=is_procedural,
        is_comparative=is_comparative,
    )


def _negative_signals_for_query(concept: str | None, q_lower: str) -> List[str]:
    """Return phrases that should be treated as negative signals for this query."""
    signals: List[str] = []
    c_lower = (concept or "").lower()

    if ("tcp" in q_lower or "tcp" in c_lower) and "handshake" in q_lower:
        signals.extend(["tls", "record protocol", "authentication protocol"])

    if "b+ tree" in q_lower or "b plus tree" in q_lower or "b-tree" in q_lower:
        signals.extend(["r tree", "generalized search trees"])

    if "virtual memory" in q_lower:
        signals.extend(["virtual machines", "virtual machine"])

    return signals


def _is_procedural_query(q_lower: str) -> bool:
    """Detect 'how to' / 'how does X work' style queries."""
    if q_lower.startswith(("how to ", "how do ", "how does ", "explain how ")):
        return True
    if " step by step" in q_lower or "steps to" in q_lower:
        return True
    if "algorithm for" in q_lower or "procedure for" in q_lower:
        return True
    return False


def _is_comparative_query(q_lower: str) -> bool:
    """Detect 'compare X and Y' / 'difference between' queries."""
    if "compare " in q_lower:
        return True
    if " vs " in q_lower or " versus " in q_lower:
        return True
    if "difference between" in q_lower:
        return True
    if "advantages of" in q_lower and "over" in q_lower:
        return True
    return False


def chunk_about_concept(chunk: "ChunkRecord", concept: str) -> bool:
    """True if the chunk is about the concept (based on key_terms)."""
    c = concept.lower().strip()
    for t in chunk.key_terms:
        if c in t.lower():
            return True
    return False


def chunk_negates_concept(chunk: "ChunkRecord", concept: str) -> bool:
    """True if the chunk clearly negates the concept (e.g. 'non-deadlock')."""
    c = concept.lower().strip()
    h = chunk.header_path.lower()
    for phrase in (f"non-{c}", f"non {c}", f"no {c}", f"without {c}"):
        if phrase in h:
            return True
    return False
