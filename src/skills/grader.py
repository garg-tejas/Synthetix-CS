from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.llm import create_client


@dataclass
class GradeResult:
    score_0_5: int
    verdict: str
    missing_points: list[str]
    incorrect_points: list[str]


def _build_prompt(
    *,
    question: str,
    reference_answer: str,
    user_answer: str,
    subject: Optional[str] = None,
    context_excerpt: Optional[str] = None,
) -> str:
    subj = subject or "computer science (operating systems, databases, or computer networks)"

    parts = [
        f"You are grading a short-answer question in {subj}.",
        "",
        "You are given:",
        "- The question.",
        "- A reference answer that reflects the key ideas.",
        "- The user's answer.",
    ]
    if context_excerpt:
        parts.append("- An optional context excerpt from the source material.")

    parts.append(
        """
Your task is to compare the user's answer to the reference answer and decide how well it captures the key ideas.

Score the answer from 0 to 5 as follows:
- 5: Completely correct. All key ideas are present and accurate.
- 4: Mostly correct. One minor idea missing or slightly inaccurate.
- 3: Partially correct. Some important ideas are missing or unclear.
- 2: Significant misunderstanding or major omissions.
- 1: Barely correct. Only a small hint of the right idea.
- 0: Entirely incorrect or off-topic.

Be strict but fair. Focus on conceptual correctness rather than exact wording.

Respond with a single JSON object with this structure:
{
  "score_0_5": <integer from 0 to 5>,
  "verdict": "correct" | "partially_correct" | "incorrect",
  "missing_points": ["..."],
  "incorrect_points": ["..."]
}

Do not include any explanation outside the JSON. The JSON must be the only content in your reply.
"""
    )

    parts.append("Question:")
    parts.append(question.strip())
    parts.append("")

    parts.append("Reference answer:")
    parts.append(reference_answer.strip())
    parts.append("")

    if context_excerpt:
        parts.append("Context excerpt:")
        parts.append(context_excerpt.strip())
        parts.append("")

    parts.append("User answer:")
    parts.append(user_answer.strip())
    parts.append("")
    parts.append("JSON:")

    return "\n".join(parts)


def grade_answer(
    *,
    question: str,
    reference_answer: str,
    user_answer: str,
    subject: Optional[str] = None,
    context_excerpt: Optional[str] = None,
) -> GradeResult:
    """
    Grade a user's answer using the configured LLM client.

    Returns a GradeResult with a 0-5 score suitable for SM-2.
    """
    prompt = _build_prompt(
        question=question,
        reference_answer=reference_answer,
        user_answer=user_answer,
        subject=subject,
        context_excerpt=context_excerpt,
    )

    client = create_client()
    raw = client.generate_single(prompt, max_tokens=256, temperature=0.1)

    score = 3
    verdict = "partially_correct"
    missing: list[str] = []
    incorrect: list[str] = []

    try:
        data: Dict[str, Any] = json.loads(raw)
        score = int(data.get("score_0_5", score))
        score = max(0, min(5, score))
        verdict = str(data.get("verdict", verdict))
        missing = list(data.get("missing_points", missing))  # type: ignore[arg-type]
        incorrect = list(data.get("incorrect_points", incorrect))  # type: ignore[arg-type]
    except Exception:
        # If the model response is not valid JSON, fall back to a neutral score.
        pass

    return GradeResult(
        score_0_5=score,
        verdict=verdict,
        missing_points=missing,
        incorrect_points=incorrect,
    )

