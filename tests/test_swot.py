from __future__ import annotations

import datetime as dt

from src.db.models import Card, ReviewAttempt, ReviewState, Topic
from src.skills.swot import MasterySWOTEngine


def _topic(name: str, id_: int) -> Topic:
    return Topic(id=id_, name=name, description=None)


def _card(id_: int, topic: Topic, topic_key: str) -> Card:
    card = Card(
        id=id_,
        topic_id=topic.id,
        question=f"Q{id_}",
        answer=f"A{id_}",
        difficulty="medium",
        question_type="definition",
        source_chunk_id=None,
        tags=None,
        topic_key=topic_key,
        generation_origin="seed",
        provenance_json=None,
    )
    card.topic = topic  # type: ignore[attr-defined]
    return card


def _state(
    *,
    user_id: int,
    card_id: int,
    due_at: dt.datetime | None,
    lapses: int = 0,
) -> ReviewState:
    return ReviewState(
        id=card_id,
        user_id=user_id,
        card_id=card_id,
        repetitions=1,
        interval_days=1,
        ease_factor=2.5,
        due_at=due_at,
        last_reviewed_at=None,
        lapses=lapses,
    )


def _attempt(*, user_id: int, card_id: int, quality: int, when: dt.datetime) -> ReviewAttempt:
    return ReviewAttempt(
        user_id=user_id,
        card_id=card_id,
        served_card_id=None,
        attempted_at=when,
        quality=quality,
        response_time_ms=900,
    )


def test_swot_engine_flags_weakness_for_low_quality_with_overdue():
    engine = MasterySWOTEngine()
    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)
    topic = _topic("os", 1)
    card = _card(1, topic, "os:deadlock")
    states = [_state(user_id=1, card_id=1, due_at=now - dt.timedelta(days=2), lapses=2)]
    attempts = [
        _attempt(user_id=1, card_id=1, quality=1, when=now - dt.timedelta(days=4)),
        _attempt(user_id=1, card_id=1, quality=2, when=now - dt.timedelta(days=3)),
        _attempt(user_id=1, card_id=1, quality=1, when=now - dt.timedelta(days=1)),
    ]

    mastery, swot = engine.compute(
        cards=[card],
        review_states=states,
        review_attempts=attempts,
        now=now,
    )

    key = ("os", "os:deadlock")
    assert mastery[key].mastery_score < 50
    assert swot[key].primary_bucket in {"weakness", "threat"}
    assert swot[key].weakness_score > swot[key].strength_score


def test_swot_engine_flags_strength_for_high_quality_no_backlog():
    engine = MasterySWOTEngine()
    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)
    topic = _topic("dbms", 1)
    card = _card(11, topic, "dbms:indexing")
    states = [_state(user_id=1, card_id=11, due_at=now + dt.timedelta(days=3), lapses=0)]
    attempts = [
        _attempt(user_id=1, card_id=11, quality=5, when=now - dt.timedelta(days=5)),
        _attempt(user_id=1, card_id=11, quality=5, when=now - dt.timedelta(days=3)),
        _attempt(user_id=1, card_id=11, quality=4, when=now - dt.timedelta(days=1)),
    ]

    mastery, swot = engine.compute(
        cards=[card],
        review_states=states,
        review_attempts=attempts,
        now=now,
    )

    key = ("dbms", "dbms:indexing")
    assert mastery[key].mastery_score > 70
    assert swot[key].strength_score >= swot[key].weakness_score
    assert swot[key].primary_bucket == "strength"
