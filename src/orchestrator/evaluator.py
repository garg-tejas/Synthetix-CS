"""
Heuristic answer evaluator: completeness and grounding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class EvalResult:
    """Result of answer evaluation."""

    is_complete: bool
    missing_aspects: List[str]
    confidence: float


_MIN_ANSWER_LEN = 30
_CITATION_PATTERN = re.compile(r"\[\d+\]")


class AnswerEvaluator:
    """Heuristic evaluator: answer length, citation presence, context use."""

    def evaluate(self, query: str, answer: str, context: str) -> EvalResult:
        """
        Heuristic check: answer long enough, has citations, context not empty.
        missing_aspects lists what failed.
        """
        missing: List[str] = []
        if len(answer.strip()) < _MIN_ANSWER_LEN:
            missing.append("answer_too_short")
        if not _CITATION_PATTERN.search(answer):
            missing.append("no_citations")
        if not (context or "").strip():
            missing.append("empty_context")
        is_complete = len(missing) == 0
        confidence = 1.0 - 0.2 * len(missing)
        return EvalResult(
            is_complete=is_complete,
            missing_aspects=missing,
            confidence=max(0.0, confidence),
        )
