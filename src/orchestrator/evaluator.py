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
        Heuristic check: answer long enough, has citations, context not empty,
        citation indices valid, and cited claims grounded in source text.
        missing_aspects lists what failed.
        """
        missing: List[str] = []
        if len(answer.strip()) < _MIN_ANSWER_LEN:
            missing.append("answer_too_short")
        if not _CITATION_PATTERN.search(answer):
            missing.append("no_citations")
        if not (context or "").strip():
            missing.append("empty_context")

        # --- Invalid citation index check ---
        # Extract all citation indices from the answer
        answer_citations: set[int] = set()
        for m in re.finditer(r"\[(\d+)\]", answer):
            try:
                answer_citations.add(int(m.group(1)))
            except ValueError:
                continue

        # Extract valid citation indices from the context
        valid_citations: set[int] = set()
        for m in re.finditer(r"^\[(\d+)\]", context or "", re.MULTILINE):
            try:
                valid_citations.add(int(m.group(1)))
            except ValueError:
                continue

        invalid_refs = answer_citations - valid_citations
        if invalid_refs:
            missing.append("invalid_citation")

        # --- Lightweight grounding check ---
        # For each valid citation used in the answer, verify the claim near
        # the citation has at least minimal word overlap with the source chunk.
        if valid_citations and answer_citations & valid_citations:
            # Build a map of citation index -> context text
            context_by_idx: dict[int, str] = {}
            chunks = re.split(r"(?=^\[\d+\])", context or "", flags=re.MULTILINE)
            for chunk_text in chunks:
                chunk_text = chunk_text.strip()
                if not chunk_text:
                    continue
                cm = re.match(r"^\[(\d+)\]", chunk_text)
                if cm:
                    try:
                        idx = int(cm.group(1))
                        context_by_idx[idx] = chunk_text.lower()
                    except ValueError:
                        continue

            ungrounded_count = 0
            for cite_idx in answer_citations & valid_citations:
                if cite_idx not in context_by_idx:
                    continue
                # Find text near this citation in the answer
                cite_pattern = re.escape(f"[{cite_idx}]")
                for m in re.finditer(cite_pattern, answer):
                    # Get ~150 chars after the citation
                    start = m.end()
                    nearby_text = answer[start : start + 150].lower()
                    # Extract content words (>3 chars)
                    nearby_words = set(re.findall(r"[a-z]{4,}", nearby_text))
                    if not nearby_words:
                        continue
                    source_text = context_by_idx[cite_idx]
                    overlap = sum(1 for w in nearby_words if w in source_text)
                    overlap_ratio = overlap / len(nearby_words)
                    if overlap_ratio < 0.15:
                        ungrounded_count += 1
                    break  # Only check first occurrence of each citation

            if ungrounded_count > 0:
                missing.append("ungrounded_citation")

        is_complete = len(missing) == 0
        confidence = 1.0 - 0.15 * len(missing)
        return EvalResult(
            is_complete=is_complete,
            missing_aspects=missing,
            confidence=max(0.0, confidence),
        )
