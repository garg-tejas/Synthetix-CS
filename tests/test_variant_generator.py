from __future__ import annotations

from src.db.models import Card, Topic
from src.skills.variant_generator import _extract_json_object, _valid_payload


def _canonical_card() -> Card:
    topic = Topic(id=1, name="os", description=None)
    card = Card(
        id=1,
        topic_id=1,
        question="Explain deadlock conditions.",
        answer="Deadlock requires mutual exclusion, hold and wait, no preemption, and circular wait.",
        difficulty="medium",
        question_type="definition",
        source_chunk_id="os::chunk_1",
        tags=None,
        topic_key="os:deadlock",
        generation_origin="seed",
        provenance_json=None,
    )
    card.topic = topic  # type: ignore[attr-defined]
    return card


def test_extract_json_object_from_fenced_content():
    raw = """```json
{
  "query": "How can deadlock be prevented in systems design?",
  "answer": "Break at least one Coffman condition.",
  "question_type": "procedural",
  "difficulty": "medium"
}
```"""
    parsed = _extract_json_object(raw)
    assert parsed is not None
    assert parsed["question_type"] == "procedural"


def test_valid_payload_rejects_same_question_text():
    canonical = _canonical_card()
    payload = {
        "query": "Explain deadlock conditions.",
        "answer": "Deadlock has four conditions.",
        "question_type": "definition",
        "difficulty": "medium",
    }
    assert _valid_payload(payload, canonical) is False


def test_valid_payload_accepts_distinct_grounded_variant():
    canonical = _canonical_card()
    payload = {
        "query": "How would you break one Coffman condition to avoid deadlock?",
        "answer": "Eliminate circular wait or allow preemption to prevent deadlock formation.",
        "question_type": "procedural",
        "difficulty": "medium",
    }
    assert _valid_payload(payload, canonical) is True
