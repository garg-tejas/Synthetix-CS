from __future__ import annotations

from typing import Annotated, List
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_active_user
from src.db.models import Card, ReviewAttempt, ReviewState, Topic, User
from src.db.session import get_db
from src.skills.quiz_service import QuizService
from src.skills.schemas import (
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizCard,
    QuizNextRequest,
    QuizNextResponse,
    QuizStatsResponse,
    TopicStats,
)


router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.get("/topics", response_model=List[TopicStats])
async def list_topics(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> List[TopicStats]:
    """
    List topics with their total card counts.
    """
    # Aggregate total cards per topic.
    result = await db.execute(
        select(Topic.name, func.count(Card.id))
        .join(Card, Card.topic_id == Topic.id)
        .group_by(Topic.name)
        .order_by(Topic.name)
    )
    rows = result.all()

    return [
        TopicStats(
            topic=name,
            total=count,
            learned=0,
            due_today=0,
            overdue=0,
        )
        for name, count in rows
    ]


@router.post("/next", response_model=QuizNextResponse)
async def get_next_quiz_cards(
    payload: QuizNextRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> QuizNextResponse:
    """
    Return the next batch of quiz cards for the current user.
    """
    svc = QuizService()

    # Load cards (and their topics) for the requested topics, if any.
    card_query = select(Card).join(Topic)
    if payload.topics:
        card_query = card_query.where(Topic.name.in_(payload.topics))
    card_result = await db.execute(card_query)
    cards = card_result.scalars().unique().all()

    # Load review states for this user.
    state_result = await db.execute(
        select(ReviewState).where(ReviewState.user_id == current_user.id)
    )
    review_states = state_result.scalars().all()

    selected_cards = svc.get_next_cards(
        user_id=current_user.id,
        cards=cards,
        review_states=review_states,
        topics=payload.topics,
        limit=payload.limit,
    )

    # Count due vs new based on review_states and due_at.
    user_state_by_card = {rs.card_id: rs for rs in review_states}
    now = dt.datetime.now(dt.timezone.utc)
    due_count = 0
    new_count = 0
    for card in selected_cards:
        rs = user_state_by_card.get(card.id)
        if rs is None:
            new_count += 1
        elif rs.due_at is not None and rs.due_at <= now:
            due_count += 1

    quiz_cards = [
        QuizCard(
            card_id=card.id,
            topic=card.topic.name if card.topic else "",  # type: ignore[union-attr]
            question=card.question,
            difficulty=card.difficulty,
            question_type=card.question_type,
        )
        for card in selected_cards
    ]

    return QuizNextResponse(cards=quiz_cards, due_count=due_count, new_count=new_count)


@router.post("/answer", response_model=QuizAnswerResponse)
async def submit_quiz_answer(
    payload: QuizAnswerRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: Request,
) -> QuizAnswerResponse:
    """
    Record a quiz answer rating and return updated schedule info.
    """
    svc = QuizService()

    # Load the card.
    card_result = await db.execute(
        select(Card).where(Card.id == payload.card_id)
    )
    card = card_result.scalar_one_or_none()
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    # Load existing review state for this user + card, if any.
    state_result = await db.execute(
        select(ReviewState).where(
            ReviewState.user_id == current_user.id,
            ReviewState.card_id == card.id,
        )
    )
    review_state = state_result.scalar_one_or_none()

    updated_state, attempt = svc.record_attempt(
        user_id=current_user.id,
        card=card,
        review_state=review_state,
        quality=payload.quality,
        response_time_ms=payload.response_time_ms,
    )

    # Persist changes.
    if review_state is None:
        db.add(updated_state)
    db.add(attempt)
    await db.commit()
    await db.refresh(updated_state)

    # RAG-style context: use source_chunk_id to pull the underlying chunk text
    # from the already loaded RAG chunks, if available.
    explanation = None
    chunks_by_id = getattr(request.app.state, "chunks_by_id", {}) or {}
    if card.source_chunk_id and card.source_chunk_id in chunks_by_id:
        chunk = chunks_by_id[card.source_chunk_id]
        text = getattr(chunk, "text", "")
        if text:
            max_len = 600
            explanation = text[:max_len] + ("…" if len(text) > max_len else "")

    return QuizAnswerResponse(
        answer=card.answer,
        explanation=explanation,
        source_chunk_id=card.source_chunk_id,
        next_due_at=updated_state.due_at.isoformat() if updated_state.due_at else None,
        interval_days=updated_state.interval_days,
    )


@router.get("/stats", response_model=QuizStatsResponse)
async def get_quiz_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> QuizStatsResponse:
    """
    Return per-topic quiz statistics for the current user.
    """
    svc = QuizService()

    # Load all cards with topics.
    card_result = await db.execute(select(Card).join(Topic))
    cards = card_result.scalars().unique().all()

    # Load all review states for this user.
    state_result = await db.execute(
        select(ReviewState).where(ReviewState.user_id == current_user.id)
    )
    review_states = state_result.scalars().all()

    stats_data = svc.get_stats(
        user_id=current_user.id,
        cards=cards,
        review_states=review_states,
    )

    topics_stats = [
        TopicStats(
            topic=entry["topic"],
            total=entry["total"],
            learned=entry["learned"],
            due_today=entry["due_today"],
            overdue=entry["overdue"],
        )
        for entry in stats_data
    ]

    return QuizStatsResponse(topics=topics_stats)

