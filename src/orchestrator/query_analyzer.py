"""
Query analyzer for intent, complexity, and decomposition.
Uses heuristics and src.rag.query_understanding for definition/procedural/comparative signals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from src.rag.query_understanding import analyze as analyze_intent


@dataclass
class QueryAnalysis:
    """Result of query analysis for the orchestrator."""

    intent: str
    complexity: str
    sub_queries: List[str]
    entities: List[str]
    requires_retrieval: bool


_SIMPLE_GREETING = re.compile(
    r"^(hi|hello|hey|thanks|thank you|bye|ok|yes|no)[\s!?.]*$",
    re.I,
)
_MULTI_PART_MARKERS = (" and ", " also ", " then ", "; ", "? ", " versus ", " vs ")


def _infer_intent(intent_result) -> str:
    if intent_result.is_definition_seeking:
        return "definition"
    if intent_result.is_comparative:
        return "comparison"
    if intent_result.is_procedural:
        return "procedural"
    return "factual"


def _infer_complexity(query: str) -> str:
    q = query.strip()
    if _SIMPLE_GREETING.match(q):
        return "simple"
    for m in _MULTI_PART_MARKERS:
        if m in q:
            return "multi-part"
    return "simple"


def _decompose(query: str) -> List[str]:
    q = query.strip()
    for sep in (" and ", " also ", " then "):
        if sep in q:
            parts = [p.strip() for p in q.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts
    for sep in ("; ", "? "):
        if sep in q:
            parts = [p.strip() for p in q.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts
    return [q]


def _extract_entities(query: str, concept: Optional[str]) -> List[str]:
    entities: List[str] = []
    if concept:
        entities.append(concept.strip())
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", query)
    for w in words:
        wl = w.lower()
        if len(wl) > 2 and wl not in ("what", "how", "why", "when", "the", "and", "for", "with", "from", "does", "explain", "define", "compare", "difference", "between"):
            if w not in entities:
                entities.append(w)
    return entities[:10]


class QueryAnalyzer:
    """Analyzes user query for intent, complexity, and sub-queries."""

    def analyze(
        self,
        query: str,
        history: Optional[List[dict]] = None,
    ) -> QueryAnalysis:
        """
        Analyze query. history is reserved for follow-up detection; not used in v0.
        """
        q = (query or "").strip()
        if not q:
            return QueryAnalysis(
                intent="factual",
                complexity="simple",
                sub_queries=[],
                entities=[],
                requires_retrieval=False,
            )
        if _SIMPLE_GREETING.match(q):
            return QueryAnalysis(
                intent="factual",
                complexity="simple",
                sub_queries=[],
                entities=[],
                requires_retrieval=False,
            )
        intent_result = analyze_intent(q)
        intent = _infer_intent(intent_result)
        complexity = _infer_complexity(q)
        sub_queries = _decompose(q) if complexity == "multi-part" else [q]
        entities = _extract_entities(q, intent_result.concept)
        return QueryAnalysis(
            intent=intent,
            complexity=complexity,
            sub_queries=sub_queries,
            entities=entities,
            requires_retrieval=True,
        )
