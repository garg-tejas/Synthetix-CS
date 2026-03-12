"""
Query analyzer for intent, complexity, and decomposition.
Uses heuristics and src.rag.query_understanding for definition/procedural/comparative signals.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from src.llm import create_client
from src.rag.query_understanding import analyze as analyze_intent

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysis:
    """Result of query analysis for the orchestrator."""

    intent: str
    complexity: str
    sub_queries: List[str]
    entities: List[str]
    requires_retrieval: bool
    reformulated_query: Optional[str] = None


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
        if len(wl) > 2 and wl not in (
            "what",
            "how",
            "why",
            "when",
            "the",
            "and",
            "for",
            "with",
            "from",
            "does",
            "explain",
            "define",
            "compare",
            "difference",
            "between",
        ):
            if w not in entities:
                entities.append(w)
    return entities[:10]


_FOLLOW_UP_PRONOUNS = re.compile(
    r"\b(it|its|they|them|their|this|that|these|those|the same|above|previous)\b",
    re.I,
)
_SHORT_QUERY_THRESHOLD = 6  # word count


def _is_follow_up(query: str, history: Optional[List[dict]]) -> bool:
    """Heuristic: query is likely a follow-up if it has pronouns/short and there's history."""
    if not history:
        return False
    q = query.strip()
    if not q:
        return False
    # Very short queries after conversation often reference prior context
    if len(q.split()) <= _SHORT_QUERY_THRESHOLD and len(history) >= 1:
        if _FOLLOW_UP_PRONOUNS.search(q):
            return True
    # Any pronoun-heavy query with history
    pronoun_hits = len(_FOLLOW_UP_PRONOUNS.findall(q))
    if pronoun_hits >= 1 and len(history) >= 1:
        return True
    return False


def _reformulate_query(query: str, history: List[dict]) -> Optional[str]:
    """Use LLM to reformulate a follow-up query into a standalone query."""
    # Build conversation context (last 3 turns max)
    recent = history[-3:]
    turns_text = "\n".join(
        f"User: {t['query']}\nAssistant: {t['answer'][:200]}" for t in recent
    )
    prompt = f"""Rewrite the follow-up question into a fully self-contained question.
Use the conversation history to resolve any pronouns or references.
Return ONLY the rewritten question, nothing else.

Conversation:
{turns_text}

Follow-up question: {query}

Rewritten standalone question:"""

    try:
        client = create_client()
        result = client.generate_single(prompt, max_tokens=150, temperature=0.0)
        reformulated = result.strip().strip('"').strip()
        if reformulated and len(reformulated) > 5:
            logger.info("Reformulated '%s' -> '%s'", query, reformulated)
            return reformulated
    except Exception:
        logger.warning("Follow-up reformulation failed for query: %s", query)
    return None


class QueryAnalyzer:
    """Analyzes user query for intent, complexity, and sub-queries."""

    def analyze(
        self,
        query: str,
        history: Optional[List[dict]] = None,
    ) -> QueryAnalysis:
        """
        Analyze query. If history is provided and query looks like a follow-up,
        reformulate it into a standalone query using the LLM.
        """
        q = (query or "").strip()
        if not q:
            return QueryAnalysis(
                intent="factual",
                complexity="simple",
                sub_queries=[],
                entities=[],
                requires_retrieval=False,
                reformulated_query=None,
            )
        if _SIMPLE_GREETING.match(q):
            return QueryAnalysis(
                intent="factual",
                complexity="simple",
                sub_queries=[],
                entities=[],
                requires_retrieval=False,
                reformulated_query=None,
            )
        # Follow-up detection and reformulation
        reformulated: Optional[str] = None
        if _is_follow_up(q, history):
            reformulated = _reformulate_query(q, history)
            if reformulated:
                q = reformulated
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
            reformulated_query=reformulated,
        )
