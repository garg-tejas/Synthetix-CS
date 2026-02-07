from __future__ import annotations

import json

from src.skills import grader


class _StubClient:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def generate_single(self, *_args, **_kwargs) -> str:
        return self.raw


def _patch_client(monkeypatch, raw: str) -> None:
    monkeypatch.setattr(grader, "create_client", lambda: _StubClient(raw))


def test_grade_answer_parses_remediation_fields(monkeypatch) -> None:
    payload = {
        "score_0_5": 2,
        "verdict": "incorrect",
        "missing_points": ["Discusses symptom but not root mechanism."],
        "incorrect_points": ["Confuses mutual exclusion with starvation."],
        "concept_summary": "Deadlock requires all Coffman conditions to hold at once.",
        "where_you_missed": [
            "You did not explain circular wait.",
            "You mixed deadlock with starvation.",
        ],
        "should_remediate": True,
    }
    _patch_client(monkeypatch, json.dumps(payload))

    result = grader.grade_answer(
        question="Explain deadlock.",
        reference_answer="Deadlock requires four Coffman conditions.",
        user_answer="Deadlock happens when CPU is overloaded.",
        subject="os",
    )

    assert result.score_0_5 == 2
    assert result.verdict == "incorrect"
    assert result.should_remediate is True
    assert result.concept_summary.startswith("Deadlock requires")
    assert len(result.where_you_missed) == 2


def test_grade_answer_forces_no_remediation_on_correct(monkeypatch) -> None:
    payload = {
        "score_0_5": 5,
        "verdict": "correct",
        "missing_points": [],
        "incorrect_points": [],
        "concept_summary": "Should not be shown.",
        "where_you_missed": ["Should not be shown."],
        "should_remediate": True,
    }
    _patch_client(monkeypatch, json.dumps(payload))

    result = grader.grade_answer(
        question="What is a semaphore?",
        reference_answer="A synchronization primitive controlling access.",
        user_answer="A synchronization primitive controlling access.",
        subject="os",
    )

    assert result.verdict == "correct"
    assert result.should_remediate is False
    assert result.concept_summary == ""
    assert result.where_you_missed == []


def test_grade_answer_fallback_on_invalid_json(monkeypatch) -> None:
    _patch_client(monkeypatch, "not-json")

    result = grader.grade_answer(
        question="What is two-phase locking?",
        reference_answer="Growing then shrinking lock phases.",
        user_answer="It means locking quickly.",
        subject="dbms",
    )

    assert result.score_0_5 == 3
    assert result.verdict == "partially_correct"
    assert result.should_remediate is True
    assert result.concept_summary != ""
    assert len(result.where_you_missed) >= 1
