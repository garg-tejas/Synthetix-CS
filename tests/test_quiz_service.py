from __future__ import annotations

import datetime as dt

from src.db.models import Card, ReviewAttempt, ReviewState, Topic
from src.skills.quiz_service import QuizSelectionConfig, QuizService


def _make_topic(name: str, id_: int = 1) -> Topic:
    return Topic(id=id_, name=name, description=None)


def _make_card(id_: int, topic: Topic) -> Card:
    card = Card(
        id=id_,
        topic_id=topic.id,
        question=f"Q{id_}",
        answer=f"A{id_}",
        difficulty="medium",
        question_type="definition",
        source_chunk_id=None,
        tags=None,
    )
    # Attach topic relationship in-memory for filtering.
    card.topic = topic  # type: ignore[attr-defined]
    return card


def _make_state(user_id: int, card_id: int, due_at: dt.datetime | None) -> ReviewState:
    return ReviewState(
        id=card_id,
        user_id=user_id,
        card_id=card_id,
        repetitions=1 if due_at else 0,
        interval_days=1 if due_at else 0,
        ease_factor=2.5,
        due_at=due_at,
        last_reviewed_at=None,
        lapses=0,
    )


def test_get_next_cards_prioritizes_due_then_new():
    svc = QuizService(QuizSelectionConfig(default_limit=10))
    topic = _make_topic("os", 1)

    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)
    past = now - dt.timedelta(days=1)
    future = now + dt.timedelta(days=1)

    c1 = _make_card(1, topic)
    c2 = _make_card(2, topic)
    c3 = _make_card(3, topic)

    # c2 is due, c1 is scheduled in the future, c3 is new (no state).
    s1 = _make_state(user_id=1, card_id=1, due_at=future)
    s2 = _make_state(user_id=1, card_id=2, due_at=past)

    cards = [c1, c2, c3]
    states = [s1, s2]

    selected = svc.get_next_cards(
        user_id=1,
        cards=cards,
        review_states=states,
        topics=None,
        limit=3,
        now=now,
    )

    # Expect: due card first (c2), then new card (c3). c1 is not yet due.
    assert [c.id for c in selected] == [2, 3]


def test_get_next_cards_filters_by_topic():
    svc = QuizService()
    topic_os = _make_topic("os", 1)
    topic_cn = _make_topic("cn", 2)

    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)
    past = now - dt.timedelta(days=1)

    c1 = _make_card(1, topic_os)
    c2 = _make_card(2, topic_cn)

    s1 = _make_state(user_id=1, card_id=1, due_at=past)
    s2 = _make_state(user_id=1, card_id=2, due_at=past)

    selected = svc.get_next_cards(
        user_id=1,
        cards=[c1, c2],
        review_states=[s1, s2],
        topics=["os"],
        limit=5,
        now=now,
    )

    assert [c.id for c in selected] == [1]


def test_get_next_cards_respects_limit():
    svc = QuizService(QuizSelectionConfig(default_limit=2))
    topic = _make_topic("os", 1)

    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)
    past = now - dt.timedelta(days=1)

    c1 = _make_card(1, topic)
    c2 = _make_card(2, topic)
    c3 = _make_card(3, topic)

    s1 = _make_state(user_id=1, card_id=1, due_at=past)

    selected = svc.get_next_cards(
        user_id=1,
        cards=[c1, c2, c3],
        review_states=[s1],
        topics=None,
        limit=2,
        now=now,
    )

    # One due card (c1), plus one new card (c2 or c3) to reach limit=2.
    assert len(selected) == 2
    assert selected[0].id == 1


def test_record_attempt_creates_state_for_new_card():
    svc = QuizService()
    topic = _make_topic("os", 1)
    card = _make_card(1, topic)
    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)

    state, attempt = svc.record_attempt(
        user_id=1,
        card=card,
        review_state=None,
        quality=5,
        response_time_ms=1234,
        now=now,
    )

    assert isinstance(state, ReviewState)
    assert isinstance(attempt, ReviewAttempt)
    assert state.user_id == 1
    assert state.card_id == card.id
    assert state.repetitions >= 1
    assert state.interval_days >= 1
    assert state.due_at is not None
    assert attempt.user_id == 1
    assert attempt.card_id == card.id
    assert attempt.served_card_id is None
    assert attempt.quality == 5
    assert attempt.response_time_ms == 1234


def test_record_attempt_tracks_served_variant_id():
    svc = QuizService()
    topic = _make_topic("os", 1)
    card = _make_card(1, topic)
    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)

    _state, attempt = svc.record_attempt(
        user_id=1,
        card=card,
        review_state=None,
        quality=3,
        served_card_id=99,
        response_time_ms=222,
        now=now,
    )
    assert attempt.card_id == 1
    assert attempt.served_card_id == 99


def test_get_stats_counts_per_topic():
    svc = QuizService()
    topic_os = _make_topic("os", 1)
    topic_cn = _make_topic("cn", 2)

    now = dt.datetime(2025, 1, 10, tzinfo=dt.timezone.utc)
    today = now
    yesterday = now - dt.timedelta(days=1)
    tomorrow = now + dt.timedelta(days=1)

    # Cards
    c1 = _make_card(1, topic_os)
    c2 = _make_card(2, topic_os)
    c3 = _make_card(3, topic_cn)

    # States: one learned and overdue in os, one due today in os, one learned in cn but future due
    s1 = _make_state(user_id=1, card_id=1, due_at=yesterday)
    s1.repetitions = 2
    s2 = _make_state(user_id=1, card_id=2, due_at=today)
    s2.repetitions = 1
    s3 = _make_state(user_id=1, card_id=3, due_at=tomorrow)
    s3.repetitions = 1

    stats = svc.get_stats(
        user_id=1,
        cards=[c1, c2, c3],
        review_states=[s1, s2, s3],
        topics=None,
        now=now,
    )

    # Convert to dict keyed by topic for easier assertions.
    by_topic = {entry["topic"]: entry for entry in stats}

    os_stats = by_topic["os"]
    assert os_stats["total"] == 2
    assert os_stats["learned"] == 2
    assert os_stats["due_today"] == 1
    assert os_stats["overdue"] == 1

    cn_stats = by_topic["cn"]
    assert cn_stats["total"] == 1
    assert cn_stats["learned"] == 1
    assert cn_stats["due_today"] == 0
    assert cn_stats["overdue"] == 0

