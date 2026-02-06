"""
Lightweight structural quality checks for generated QA pairs.

This module intentionally avoids topic/keyword heuristics. Interview relevance
should come from LLM review, while this layer only catches malformed entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.rag.index import ChunkRecord


VALID_QUESTION_TYPES = {"definition", "procedural", "comparative", "factual"}
VALID_DIFFICULTY = {"easy", "medium", "hard"}


@dataclass
class InterviewQualityAssessment:
    score: int
    keep: bool
    reasons: list[str]


def assess_interview_quality(
    question: Dict[str, Any],
    *,
    chunk: Optional[ChunkRecord] = None,
    min_score: int = 70,
) -> InterviewQualityAssessment:
    """
    Score structural quality from 0-100 (schema/length/coherence only).

    This function is deliberately keyword-agnostic and does not infer interview
    depth from specific words or prefixes.
    """
    _ = chunk
    reasons: list[str] = []

    query = str(question.get("query") or "").strip()
    answer = str(question.get("answer") or "").strip()
    question_type = str(question.get("question_type") or "").strip().lower()
    difficulty = str(question.get("difficulty") or "").strip().lower()
    atomic_facts = question.get("atomic_facts") or []

    if not query:
        return InterviewQualityAssessment(score=0, keep=False, reasons=["missing query"])
    if not answer:
        return InterviewQualityAssessment(score=0, keep=False, reasons=["missing answer"])

    score = 100

    # Schema validity.
    if question_type not in VALID_QUESTION_TYPES:
        score -= 30
        reasons.append("invalid question_type")
    if difficulty not in VALID_DIFFICULTY:
        score -= 20
        reasons.append("invalid difficulty")

    # Query quality floor (not semantic depth).
    q_len = len(query)
    if q_len < 12:
        score -= 35
        reasons.append("query too short")
    elif q_len < 20:
        score -= 20
        reasons.append("query is terse")
    elif q_len > 280:
        score -= 10
        reasons.append("query too long")

    # Answer quality floor.
    a_len = len(answer)
    if a_len < 50:
        score -= 35
        reasons.append("answer too short")
    elif a_len < 90:
        score -= 15
        reasons.append("answer lacks detail")
    elif a_len > 1400:
        score -= 15
        reasons.append("answer too long")

    # Atomic facts shape.
    if not isinstance(atomic_facts, list):
        score -= 20
        reasons.append("atomic_facts is not a list")
    else:
        facts = [str(x).strip() for x in atomic_facts if str(x).strip()]
        if len(facts) < 2:
            score -= 20
            reasons.append("needs at least 2 atomic_facts")
        elif len(facts) > 6:
            score -= 6
            reasons.append("too many atomic_facts")
        short_facts = [f for f in facts if len(f) < 5]
        if short_facts:
            score -= 8
            reasons.append("atomic_facts too terse")

    # Guard against accidental instruction leakage.
    q_lower = query.lower()
    if q_lower.startswith("generate ") or "return only json" in q_lower:
        score -= 30
        reasons.append("query appears to be an instruction, not a real question")

    score = max(0, min(100, score))
    keep = score >= min_score
    if not keep and not reasons:
        reasons.append("structural quality below threshold")

    return InterviewQualityAssessment(score=score, keep=keep, reasons=reasons)

