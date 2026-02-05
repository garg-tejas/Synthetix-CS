from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class SupportsSM2State(Protocol):
    """
    Minimal protocol for SM-2 state.

    This lets us operate on ORM models (ReviewState) or simple
    dataclasses in tests, as long as they expose the expected fields.
    """

    repetitions: int
    interval_days: int
    ease_factor: float
    due_at: Optional[dt.datetime]
    last_reviewed_at: Optional[dt.datetime]
    lapses: int


@dataclass
class SM2Config:
    """Config values for the SM-2 scheduler."""

    min_ease_factor: float = 1.3
    initial_ease_factor: float = 2.5


class SM2Scheduler:
    """
    Classic SM-2 spaced repetition scheduler.

    Ported from the original SuperMemo-2 algorithm, adapted to work with
    our ReviewState model:

        - quality is an integer in [0, 5]
        - quality < 3 is considered a failed recall
        - ease factor (EF) is adjusted after each review
        - interval is in days and determines the next due_at
    """

    def __init__(self, config: Optional[SM2Config] = None) -> None:
        self.config = config or SM2Config()

    def compute_next(
        self,
        state: SupportsSM2State,
        quality: int,
        *,
        now: Optional[dt.datetime] = None,
    ) -> SupportsSM2State:
        """
        Update the given review state in-place using SM-2 and return it.
        """
        if quality < 0 or quality > 5:
            raise ValueError("quality must be between 0 and 5")

        now = now or dt.datetime.now(dt.timezone.utc)

        ef = state.ease_factor or self.config.initial_ease_factor
        reps = int(state.repetitions or 0)
        interval = int(state.interval_days or 0)
        lapses = int(state.lapses or 0)

        if quality < 3:
            # Failed recall: reset repetitions, short interval, count lapse.
            reps = 0
            lapses += 1
            interval = 1
        else:
            # Successful recall: adjust ease factor.
            q_delta = 5 - quality
            ef = ef + (0.1 - q_delta * (0.08 + q_delta * 0.02))
            if ef < self.config.min_ease_factor:
                ef = self.config.min_ease_factor

            # Increment repetitions and compute next interval.
            reps += 1
            if reps == 1:
                interval = 1
            elif reps == 2:
                interval = 6
            else:
                interval = max(1, round(interval * ef)) if interval > 0 else 6

        state.repetitions = reps
        state.interval_days = interval
        state.ease_factor = ef
        state.last_reviewed_at = now
        state.due_at = now + dt.timedelta(days=interval)
        state.lapses = lapses

        return state

