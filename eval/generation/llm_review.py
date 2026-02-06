"""
LLM-based review for generated interview questions.

This module adds a second pass where an LLM evaluates each generated question
for interview depth and can rewrite shallow prompts into stronger variants.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Dict, List

from src.llm.client import ModelScopeClient
from src.rag.index import ChunkRecord
from .prompts import build_bulk_qa_scoring_prompt, build_qa_review_prompt


VALID_QUESTION_TYPES = {"definition", "procedural", "comparative", "factual"}
VALID_DIFFICULTY = {"easy", "medium", "hard"}


@dataclass
class LLMReviewOutcome:
    success: bool
    accepted: List[Dict[str, Any]]
    rejected: List[Dict[str, Any]]


@dataclass
class LLMBatchScoreOutcome:
    success: bool
    scored: List[Dict[str, Any]]
    failed_indexes: List[int]


def _truncate_error(error: Exception, max_len: int = 240) -> str:
    text = f"{type(error).__name__}: {error}"
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _extract_json(response: str) -> Dict[str, Any] | None:
    if not response or not response.strip():
        return None

    raw = response.strip()
    candidates = [raw]

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fenced:
        candidates.insert(0, fenced.group(1))

    if not raw.startswith("{"):
        generic = re.search(r"\{.*\}", raw, re.DOTALL)
        if generic:
            candidates.append(generic.group(0))

    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_rewrite(original: Dict[str, Any], revised: Dict[str, Any]) -> Dict[str, Any] | None:
    query = str(revised.get("query") or "").strip()
    answer = str(revised.get("answer") or "").strip()
    question_type = str(revised.get("question_type") or "").strip().lower()
    difficulty = str(revised.get("difficulty") or "").strip().lower()
    atomic_facts = revised.get("atomic_facts")

    if not query or not answer:
        return None
    if question_type not in VALID_QUESTION_TYPES:
        return None
    if difficulty not in VALID_DIFFICULTY:
        return None
    if not isinstance(atomic_facts, list) or len(atomic_facts) < 2:
        return None

    rewritten = dict(original)
    rewritten["query"] = query
    rewritten["answer"] = answer
    rewritten["question_type"] = question_type
    rewritten["difficulty"] = difficulty
    rewritten["atomic_facts"] = [str(x).strip() for x in atomic_facts if str(x).strip()]
    rewritten["llm_rewritten"] = True
    return rewritten


def review_questions_with_llm(
    *,
    questions: List[Dict[str, Any]],
    chunk: ChunkRecord,
    llm_client: ModelScopeClient,
    min_score: int = 70,
    allow_rewrite: bool = True,
    max_retries: int = 2,
) -> LLMReviewOutcome:
    """
    Review generated questions and keep only interview-suitable entries.

    The LLM can keep, rewrite, or reject each question.
    """
    if not questions:
        return LLMReviewOutcome(success=True, accepted=[], rejected=[])

    review_payload: List[Dict[str, Any]] = []
    for i, q in enumerate(questions):
        review_payload.append(
            {
                "index": i,
                "query": q.get("query"),
                "question_type": q.get("question_type"),
                "difficulty": q.get("difficulty"),
                "source_header": q.get("source_header"),
            }
        )

    prompt = build_qa_review_prompt(
        chunk=chunk,
        candidate_questions=review_payload,
        min_score=min_score,
        allow_rewrite=allow_rewrite,
    )

    for attempt in range(max_retries):
        try:
            raw = llm_client.generate_single(
                prompt,
                max_tokens=1800,
                temperature=0.1,
                stop=["\n\n\n", "---"],
            )
        except Exception as e:
            print(
                f"Warning: LLM review request failed "
                f"(attempt {attempt + 1}/{max_retries}): {_truncate_error(e)}"
            )
            continue

        parsed = _extract_json(raw)
        if not parsed:
            print(
                f"Warning: LLM review returned non-JSON/invalid JSON "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            continue

        results = parsed.get("results")
        if not isinstance(results, list):
            print(
                f"Warning: LLM review response missing 'results' list "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            continue

        result_by_idx: Dict[int, Dict[str, Any]] = {}
        for entry in results:
            if not isinstance(entry, dict):
                continue
            idx = _safe_int(entry.get("index"), default=-1)
            if idx < 0:
                continue
            result_by_idx[idx] = entry

        accepted: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        for idx, original in enumerate(questions):
            entry = result_by_idx.get(idx)
            if not entry:
                rejected_q = dict(original)
                rejected_q["llm_review_decision"] = "reject"
                rejected_q["llm_interview_score"] = 0
                rejected_q["llm_interview_reasons"] = ["missing LLM review result"]
                rejected.append(rejected_q)
                continue

            decision = str(entry.get("decision") or "reject").strip().lower()
            if decision not in {"keep", "rewrite", "reject"}:
                decision = "reject"

            score = max(0, min(100, _safe_int(entry.get("score"), default=0)))
            reasons_raw = entry.get("reasons")
            if isinstance(reasons_raw, list):
                reasons = [str(x).strip() for x in reasons_raw if str(x).strip()]
            else:
                reasons = []

            working = dict(original)
            if decision == "rewrite":
                revised_payload = entry.get("revised")
                if allow_rewrite and isinstance(revised_payload, dict):
                    rewritten = _coerce_rewrite(working, revised_payload)
                    if rewritten is not None:
                        working = rewritten
                    else:
                        decision = "reject"
                        reasons.append("invalid rewrite payload from LLM")
                else:
                    decision = "reject"
                    reasons.append("rewrite requested but rewrite payload missing")

            working["llm_review_decision"] = decision
            working["llm_interview_score"] = score
            if reasons:
                working["llm_interview_reasons"] = reasons

            if decision in {"keep", "rewrite"} and score >= min_score:
                accepted.append(working)
            else:
                rejected.append(working)

        return LLMReviewOutcome(success=True, accepted=accepted, rejected=rejected)

    # Hard failure: caller can decide fallback strategy.
    return LLMReviewOutcome(success=False, accepted=[], rejected=[])


def score_questions_batch_with_llm(
    *,
    questions: List[Dict[str, Any]],
    llm_client: ModelScopeClient,
    min_score: int = 70,
    allow_rewrite: bool = False,
    max_retries: int = 2,
) -> LLMBatchScoreOutcome:
    """
    Bulk-score existing questions with a single sequential LLM request.
    """
    if not questions:
        return LLMBatchScoreOutcome(success=True, scored=[], failed_indexes=[])

    review_payload: List[Dict[str, Any]] = []
    for i, q in enumerate(questions):
        review_payload.append(
            {
                "index": i,
                "query": q.get("query"),
                "question_type": q.get("question_type"),
                "difficulty": q.get("difficulty"),
                "source_subject": q.get("source_subject"),
                "source_header": q.get("source_header"),
            }
        )

    prompt = build_bulk_qa_scoring_prompt(
        candidate_questions=review_payload,
        min_score=min_score,
        allow_rewrite=allow_rewrite,
    )

    batch_errors: List[str] = []
    for attempt in range(max_retries):
        try:
            raw = llm_client.generate_single(
                prompt,
                max_tokens=2200,
                temperature=0.1,
                stop=["\n\n\n", "---"],
            )
        except Exception as e:
            msg = (
                f"LLM scoring request failed "
                f"(attempt {attempt + 1}/{max_retries}): {_truncate_error(e)}"
            )
            batch_errors.append(msg)
            print(f"Warning: {msg}")
            continue

        parsed = _extract_json(raw)
        if not parsed:
            msg = (
                f"LLM scoring returned non-JSON/invalid JSON "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            batch_errors.append(msg)
            print(f"Warning: {msg}")
            continue
        results = parsed.get("results")
        if not isinstance(results, list):
            msg = (
                f"LLM scoring response missing 'results' list "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            batch_errors.append(msg)
            print(f"Warning: {msg}")
            continue

        result_by_idx: Dict[int, Dict[str, Any]] = {}
        for entry in results:
            if not isinstance(entry, dict):
                continue
            idx = _safe_int(entry.get("index"), default=-1)
            if idx < 0:
                continue
            result_by_idx[idx] = entry

        scored: List[Dict[str, Any]] = []
        failed_indexes: List[int] = []
        for idx, original in enumerate(questions):
            entry = result_by_idx.get(idx)
            if not entry:
                failed_indexes.append(idx)
                failed = dict(original)
                failed["llm_review_decision"] = "reject"
                failed["llm_interview_score"] = 0
                failed["llm_interview_reasons"] = ["missing LLM score result"]
                failed["quality_score"] = 0
                scored.append(failed)
                continue

            decision = str(entry.get("decision") or "reject").strip().lower()
            if decision not in {"keep", "rewrite", "reject"}:
                decision = "reject"
            score = max(0, min(100, _safe_int(entry.get("score"), default=0)))
            reasons_raw = entry.get("reasons")
            if isinstance(reasons_raw, list):
                reasons = [str(x).strip() for x in reasons_raw if str(x).strip()]
            else:
                reasons = []

            working = dict(original)
            if decision == "rewrite":
                revised_payload = entry.get("revised")
                if allow_rewrite and isinstance(revised_payload, dict):
                    rewritten = _coerce_rewrite(working, revised_payload)
                    if rewritten is not None:
                        working = rewritten
                    else:
                        decision = "reject"
                        reasons.append("invalid rewrite payload from LLM")
                else:
                    decision = "reject"
                    reasons.append("rewrite payload missing or rewrite disabled")

            working["llm_review_decision"] = decision
            working["llm_interview_score"] = score
            if reasons:
                working["llm_interview_reasons"] = reasons
            working["quality_score"] = score
            scored.append(working)

        return LLMBatchScoreOutcome(
            success=True,
            scored=scored,
            failed_indexes=failed_indexes,
        )

    # Request-level failure.
    failed: List[Dict[str, Any]] = []
    reason = (
        "LLM scoring request failed"
        if not batch_errors
        else " | ".join(batch_errors[-2:])
    )
    for q in questions:
        row = dict(q)
        row["llm_review_decision"] = "reject"
        row["llm_interview_score"] = 0
        row["llm_interview_reasons"] = [reason]
        row["quality_score"] = 0
        failed.append(row)
    return LLMBatchScoreOutcome(
        success=False,
        scored=failed,
        failed_indexes=list(range(len(questions))),
    )
