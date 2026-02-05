from __future__ import annotations

import datetime as dt

from src.db.models import ReviewState
from src.skills.scheduler import SM2Scheduler


def _make_state() -> ReviewState:
    # Plain ORM instance detached from any session is fine for unit testing.
    state = ReviewState(
        id=1,
        user_id=1,
        card_id=1,
        repetitions=0,
        interval_days=0,
        ease_factor=2.5,
        due_at=None,
        last_reviewed_at=None,
        lapses=0,
    )
    return state


def test_sm2_first_success_review():
    scheduler = SM2Scheduler()
    state = _make_state()
    now = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)

    updated = scheduler.compute_next(state, quality=5, now=now)

    assert updated.repetitions == 1
    assert updated.interval_days == 1
    assert updated.ease_factor > 2.5
    assert updated.last_reviewed_at == now
    assert updated.due_at == now + dt.timedelta(days=1)
    assert updated.lapses == 0


def test_sm2_second_success_review():
    scheduler = SM2Scheduler()
    state = _make_state()
    now = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)

    # First successful review
    state = scheduler.compute_next(state, quality=5, now=now)
    # Second successful review
    updated = scheduler.compute_next(state, quality=5, now=now)

    assert updated.repetitions == 2
    assert updated.interval_days == 6
    assert updated.ease_factor > 2.5
    assert updated.due_at == now + dt.timedelta(days=6)


def test_sm2_failed_review_increments_lapses_and_resets_interval():
    scheduler = SM2Scheduler()
    state = _make_state()
    now = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)

    # Simulate a couple of successful reviews first
    state = scheduler.compute_next(state, quality=5, now=now)
    state = scheduler.compute_next(state, quality=5, now=now)

    # Now a failed recall
    updated = scheduler.compute_next(state, quality=1, now=now)

    assert updated.repetitions == 0
    assert updated.interval_days == 1
    assert updated.lapses == 1
    assert updated.due_at == now + dt.timedelta(days=1)

