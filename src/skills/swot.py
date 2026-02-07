from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Card, ReviewAttempt, ReviewState, UserTopicMastery, UserTopicSWOT


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _topic_identity(card: Card) -> Tuple[str, str]:
    subject = "unknown"
    if getattr(card, "topic", None) is not None and getattr(card.topic, "name", None):
        subject = str(card.topic.name).strip().lower()
    topic_key = (card.topic_key or "").strip().lower()
    if not topic_key:
        topic_key = f"{subject}:core"
    return subject, topic_key


@dataclass
class MasterySnapshot:
    subject: str
    topic_key: str
    attempt_count: int
    avg_quality: float
    due_count: int
    overdue_count: int
    lapse_count: int
    recent_trend: float
    mastery_score: float
    last_reviewed_at: Optional[dt.datetime]


@dataclass
class SWOTSnapshot:
    subject: str
    topic_key: str
    strength_score: float
    weakness_score: float
    opportunity_score: float
    threat_score: float
    primary_bucket: str
    rationale: str
    source: str = "rule_hybrid"


class MasterySWOTEngine:
    """
    Rule-first mastery and SWOT scoring.

    Deterministic signals are authoritative:
    - attempts + avg quality
    - due/overdue pressure
    - lapse history
    - short-term trend
    """

    def compute(
        self,
        *,
        cards: Iterable[Card],
        review_states: Iterable[ReviewState],
        review_attempts: Iterable[ReviewAttempt],
        now: Optional[dt.datetime] = None,
    ) -> tuple[dict[tuple[str, str], MasterySnapshot], dict[tuple[str, str], SWOTSnapshot]]:
        now = now or dt.datetime.now(dt.timezone.utc)
        card_by_id = {card.id: card for card in cards}
        if not card_by_id:
            return {}, {}

        topic_for_card = {
            card_id: _topic_identity(card)
            for card_id, card in card_by_id.items()
        }

        attempts_by_topic: dict[tuple[str, str], list[ReviewAttempt]] = {}
        for attempt in review_attempts:
            topic = topic_for_card.get(attempt.card_id)
            if topic is None:
                continue
            attempts_by_topic.setdefault(topic, []).append(attempt)

        states_by_topic: dict[tuple[str, str], list[ReviewState]] = {}
        for state in review_states:
            topic = topic_for_card.get(state.card_id)
            if topic is None:
                continue
            states_by_topic.setdefault(topic, []).append(state)

        active_topics = set(attempts_by_topic.keys()) | set(states_by_topic.keys())
        mastery_out: dict[tuple[str, str], MasterySnapshot] = {}
        swot_out: dict[tuple[str, str], SWOTSnapshot] = {}

        for topic in active_topics:
            topic_attempts = sorted(
                attempts_by_topic.get(topic, []),
                key=lambda a: a.attempted_at,
            )
            topic_states = states_by_topic.get(topic, [])

            attempt_count = len(topic_attempts)
            avg_quality = mean(a.quality for a in topic_attempts) if topic_attempts else 0.0
            recent = topic_attempts[-3:]
            recent_avg = mean(a.quality for a in recent) if recent else avg_quality
            recent_trend = recent_avg - avg_quality
            last_reviewed_at = topic_attempts[-1].attempted_at if topic_attempts else None

            lapse_count = sum(max(0, s.lapses) for s in topic_states)
            due_count = 0
            overdue_count = 0
            for state in topic_states:
                if state.due_at is None:
                    continue
                if state.due_at <= now:
                    due_count += 1
                if state.due_at.date() < now.date():
                    overdue_count += 1

            # Mastery blends quality, stability (low lapses), momentum, and overdue pressure.
            quality_norm = avg_quality / 5.0 if attempt_count else 0.0
            lapse_ratio = min(1.0, lapse_count / max(1.0, float(attempt_count)))
            trend_component = _clamp((recent_trend / 2.0 + 1.0) * 10.0, 0.0, 20.0)
            overdue_penalty = min(30.0, overdue_count * 6.0)
            mastery_score = _clamp(
                quality_norm * 60.0
                + (1.0 - lapse_ratio) * 20.0
                + trend_component
                - overdue_penalty
            )

            subject, topic_key = topic
            mastery_snapshot = MasterySnapshot(
                subject=subject,
                topic_key=topic_key,
                attempt_count=attempt_count,
                avg_quality=round(avg_quality, 3),
                due_count=due_count,
                overdue_count=overdue_count,
                lapse_count=lapse_count,
                recent_trend=round(recent_trend, 3),
                mastery_score=round(mastery_score, 3),
                last_reviewed_at=last_reviewed_at,
            )
            mastery_out[topic] = mastery_snapshot

            # SWOT rule-authoritative scoring.
            exposure = min(1.0, attempt_count / 6.0)
            strength = _clamp(mastery_score * (1.0 - min(1.0, overdue_count / max(1, due_count + 1)) * 0.4))
            weakness = _clamp((100.0 - mastery_score) * 0.65 + lapse_ratio * 35.0)
            opportunity = _clamp((1.0 - exposure) * 60.0 + max(0.0, 70.0 - mastery_score) * 0.4)
            threat = _clamp(min(70.0, overdue_count * 14.0) + max(0.0, -recent_trend) * 12.0)

            bucket_scores = {
                "strength": strength,
                "weakness": weakness,
                "opportunity": opportunity,
                "threat": threat,
            }
            primary_bucket = max(bucket_scores, key=bucket_scores.get)
            rationale = (
                f"mastery={mastery_score:.1f}, avg_quality={avg_quality:.2f}, "
                f"attempts={attempt_count}, lapses={lapse_count}, "
                f"due={due_count}, overdue={overdue_count}, trend={recent_trend:.2f}"
            )
            swot_out[topic] = SWOTSnapshot(
                subject=subject,
                topic_key=topic_key,
                strength_score=round(strength, 3),
                weakness_score=round(weakness, 3),
                opportunity_score=round(opportunity, 3),
                threat_score=round(threat, 3),
                primary_bucket=primary_bucket,
                rationale=rationale,
            )

        return mastery_out, swot_out


class MasterySWOTRepository:
    async def upsert(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        mastery: dict[tuple[str, str], MasterySnapshot],
        swot: dict[tuple[str, str], SWOTSnapshot],
    ) -> None:
        keys = sorted(set(mastery.keys()) | set(swot.keys()))
        if not keys:
            return

        subjects = sorted({subject for subject, _ in keys})
        topic_keys = sorted({topic_key for _, topic_key in keys})

        mastery_result = await db.execute(
            select(UserTopicMastery).where(
                and_(
                    UserTopicMastery.user_id == user_id,
                    UserTopicMastery.subject.in_(subjects),
                    UserTopicMastery.topic_key.in_(topic_keys),
                )
            )
        )
        swot_result = await db.execute(
            select(UserTopicSWOT).where(
                and_(
                    UserTopicSWOT.user_id == user_id,
                    UserTopicSWOT.subject.in_(subjects),
                    UserTopicSWOT.topic_key.in_(topic_keys),
                )
            )
        )
        mastery_rows = {
            (row.subject, row.topic_key): row
            for row in mastery_result.scalars().all()
        }
        swot_rows = {
            (row.subject, row.topic_key): row
            for row in swot_result.scalars().all()
        }
        now = dt.datetime.utcnow()

        for key, snap in mastery.items():
            row = mastery_rows.get(key)
            if row is None:
                row = UserTopicMastery(
                    user_id=user_id,
                    subject=snap.subject,
                    topic_key=snap.topic_key,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            row.attempt_count = snap.attempt_count
            row.avg_quality = snap.avg_quality
            row.due_count = snap.due_count
            row.overdue_count = snap.overdue_count
            row.lapse_count = snap.lapse_count
            row.recent_trend = snap.recent_trend
            row.mastery_score = snap.mastery_score
            row.last_reviewed_at = snap.last_reviewed_at
            row.updated_at = now

        for key, snap in swot.items():
            row = swot_rows.get(key)
            if row is None:
                row = UserTopicSWOT(
                    user_id=user_id,
                    subject=snap.subject,
                    topic_key=snap.topic_key,
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
            row.strength_score = snap.strength_score
            row.weakness_score = snap.weakness_score
            row.opportunity_score = snap.opportunity_score
            row.threat_score = snap.threat_score
            row.primary_bucket = snap.primary_bucket
            row.rationale = snap.rationale
            row.source = snap.source
            row.updated_at = now


async def refresh_user_swot(
    *,
    db: AsyncSession,
    user_id: int,
    cards: list[Card],
    review_states: list[ReviewState],
    review_attempts: list[ReviewAttempt],
    now: Optional[dt.datetime] = None,
) -> tuple[dict[tuple[str, str], MasterySnapshot], dict[tuple[str, str], SWOTSnapshot]]:
    engine = MasterySWOTEngine()
    repo = MasterySWOTRepository()
    mastery, swot = engine.compute(
        cards=cards,
        review_states=review_states,
        review_attempts=review_attempts,
        now=now,
    )
    await repo.upsert(
        db=db,
        user_id=user_id,
        mastery=mastery,
        swot=swot,
    )
    return mastery, swot
