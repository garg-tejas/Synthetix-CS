"""
Lightweight query understanding for retrieval bias.

Detects definition-seeking queries ("what is X", "define X", etc.) and
optionally extracts the concept. Used to boost definition-type chunks
when appropriate, and to downrank chunks that contradict the query.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from .index import ChunkRecord


@dataclass
class QueryIntent:
    """Result of query analysis."""

    is_definition_seeking: bool
    concept: str | None  # extracted concept, if any
    # Heuristic negative signals that should *downrank or filter* chunks
    # for this query (e.g. TLS when asking about TCP handshake).
    negative_signals: List[str] | None = None
    # Additional coarse-grained intent flags used to bias retrieval:
    # - procedural: "how to", "how does X work", "explain how"
    # - comparative: "compare X and Y", "difference between"
    is_procedural: bool = False
    is_comparative: bool = False

    def __post_init__(self) -> None:
        if self.negative_signals is None:
            self.negative_signals = []
    negative_signals: List[str] = None  # terms to downrank

    def __post_init__(self):
        if self.negative_signals is None:
            self.negative_signals = []


# Patterns (pattern, group index for concept). Case-insensitive.
_DEFINITION_PATTERNS: List[Tuple[re.Pattern[str], int]] = [
    (re.compile(r"\bwhat\s+is\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bdefine\s+(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bexplain\s+(?:what\s+is\s+)?(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bmeaning\s+of\s+(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"\bdescribe\s+(?:what\s+is\s+)?(?:a\s+|an\s+|the\s+)?(.+?)(?:\?|$)", re.I), 1),
    (re.compile(r"(.+?)\s+definition\s*$", re.I), 1),
]


def analyze(query: str) -> QueryIntent:
    """
    Analyze query for intent. Sets is_definition_seeking and optionally
    extracts the concept (e.g. "deadlock" from "what is a deadlock?").
    """
    q = query.strip()
    q_lower = q.lower()
    concept: str | None = None

    is_procedural = _is_procedural_query(q_lower)
    is_comparative = _is_comparative_query(q_lower)

    # 1) Definition‑seeking patterns
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

    # 2) Non‑definition queries that we still want heuristics for
    negative = _negative_signals_for_query(None, q_lower)
    return QueryIntent(
        is_definition_seeking=False,
        concept=None,
        negative_signals=negative,
        is_procedural=is_procedural,
        is_comparative=is_comparative,
    )


def _negative_signals_for_query(concept: str | None, q_lower: str) -> List[str]:
    """
    Return a list of phrases that should be treated as negative signals
    for this query (and optional concept).

    This is deliberately small and surgical – only for cases where we
    *know* certain concepts are confusers (e.g. TLS vs TCP handshake).
    """
    signals: List[str] = []
    c_lower = (concept or "").lower()

    # TCP 3‑way handshake: we want to avoid TLS handshake / auth protocol.
    if ("tcp" in q_lower or "tcp" in c_lower) and "handshake" in q_lower:
        signals.extend(
            [
                "tls",
                "record protocol",
                "authentication protocol",
            ]
        )

    # B+‑tree insertion / deletion: avoid R‑tree / generalized search tree only riffs.
    if "b+ tree" in q_lower or "b plus tree" in q_lower or "b-tree" in q_lower:
        signals.extend(
            [
                "r tree",
                "generalized search trees",
            ]
        )

    # Virtual memory: avoid VM‑centric virtualization detours for "virtual machines".
    if "virtual memory" in q_lower:
        signals.extend(
            [
                "virtual machines",
                "virtual machine",
            ]
        )

    return signals


def _is_procedural_query(q_lower: str) -> bool:
    """Heuristic: detect 'how to' / 'how does X work' style queries."""
    if q_lower.startswith("how to "):
        return True
    if q_lower.startswith("how do "):
        return True
    if q_lower.startswith("how does "):
        return True
    if q_lower.startswith("explain how "):
        return True
    if " step by step" in q_lower or "steps to" in q_lower:
        return True
    if "algorithm for" in q_lower or "procedure for" in q_lower:
        return True
    return False


def _is_comparative_query(q_lower: str) -> bool:
    """Heuristic: detect 'compare X and Y' / 'difference between' queries."""
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
    """True if the chunk is about the concept (key_terms only). Header is noisier."""
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
