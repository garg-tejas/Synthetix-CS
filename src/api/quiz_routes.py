from __future__ import annotations

from typing import Annotated, List
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_active_user
from src.db.models import Card, ReviewAttempt, ReviewState, Topic, User
from src.db.session import get_db
from src.skills.quiz_service import QuizService
from src.skills.grader import grade_answer
from src.skills.path_planner import PathNode
from src.skills.session_service import QuizSessionService, QuizSessionState
from src.skills.swot import refresh_user_swot
from src.skills.variant_generator import VariantGenerator
from src.skills.schemas import (
    LearningPathNode,
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizCard,
    QuizNextRequest,
    QuizNextResponse,
    QuizSessionAnswerRequest,
    QuizSessionAnswerResponse,
    QuizSessionFinishResponse,
    QuizSessionStartRequest,
    QuizSessionStartResponse,
    QuizStatsResponse,
    SessionProgress,
    TopicStats,
)


router = APIRouter(prefix="/api/quiz", tags=["quiz"])


async def _refresh_swot_snapshot(
    *,
    db: AsyncSession,
    user_id: int,
    cards: list[Card],
) -> None:
    if not cards:
        return
    card_ids = [card.id for card in cards]
    states_result = await db.execute(
        select(ReviewState).where(
            ReviewState.user_id == user_id,
            ReviewState.card_id.in_(card_ids),
        )
    )
    attempts_result = await db.execute(
        select(ReviewAttempt).where(
            ReviewAttempt.user_id == user_id,
            ReviewAttempt.card_id.in_(card_ids),
        )
    )
    review_states = states_result.scalars().all()
    review_attempts = attempts_result.scalars().all()
    await refresh_user_swot(
        db=db,
        user_id=user_id,
        cards=cards,
        review_states=review_states,
        review_attempts=review_attempts,
    )
    await db.commit()


def _quiz_sessions_store(request: Request) -> dict[str, QuizSessionState]:
    store = getattr(request.app.state, "quiz_sessions", None)
    if store is None:
        store = {}
        request.app.state.quiz_sessions = store
    return store


def _to_quiz_card(card: Card, *, canonical_card_id: int | None = None) -> QuizCard:
    canonical_id = canonical_card_id
    if canonical_id is None:
        canonical_id = card.variant_of_card_id or card.id
    return QuizCard(
        card_id=card.id,
        canonical_card_id=canonical_id,
        is_variant=card.id != canonical_id,
        topic=card.topic.name if card.topic else "",  # type: ignore[union-attr]
        question=card.question,
        difficulty=card.difficulty,
        question_type=card.question_type,
    )


def _to_path_nodes(nodes: list[PathNode]) -> list[LearningPathNode]:
    return [
        LearningPathNode(
            subject=node.subject,
            topic_key=node.topic_key,
            display_name=node.display_name,
            mastery_score=node.mastery_score,
            swot_bucket=node.swot_bucket,
            priority_score=node.priority_score,
        )
        for node in nodes
    ]


def _progress(state: QuizSessionState) -> SessionProgress:
    return SessionProgress(
        current_index=state.cursor,
        total=state.total,
        completed=state.completed,
    )


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
    request: Request,
) -> QuizNextResponse:
    """
    Return the next batch of quiz cards for the current user.
    """
    svc = QuizService()

    # Load cards (and their topics) for the requested topics, if any.
    card_query = select(Card).join(Topic).options(selectinload(Card.topic))
    if payload.topics:
        card_query = card_query.where(Topic.name.in_(payload.topics))
    card_result = await db.execute(card_query)
    cards = card_result.scalars().unique().all()

    # Load review states for this user.
    state_result = await db.execute(
        select(ReviewState).where(ReviewState.user_id == current_user.id)
    )
    review_states = state_result.scalars().all()

    await _refresh_swot_snapshot(
        db=db,
        user_id=current_user.id,
        cards=cards,
    )

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
    variant_generator = VariantGenerator(
        chunks_by_id=getattr(request.app.state, "chunks_by_id", {}) or {}
    )
    quiz_cards: list[QuizCard] = []
    for card in selected_cards:
        rs = user_state_by_card.get(card.id)
        is_due = rs is not None and rs.due_at is not None and rs.due_at <= now
        if rs is None:
            new_count += 1
        elif is_due:
            due_count += 1

        served = card
        if is_due:
            served = await variant_generator.select_or_create_variant(
                db=db,
                user_id=current_user.id,
                canonical_card=card,
            )
            if served.topic is None and card.topic is not None:  # type: ignore[union-attr]
                served.topic = card.topic  # type: ignore[assignment]
        quiz_cards.append(_to_quiz_card(served, canonical_card_id=card.id))

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

    # Load served card.
    served_result = await db.execute(
        select(Card)
        .options(selectinload(Card.topic))
        .where(Card.id == payload.card_id)
    )
    served_card = served_result.scalar_one_or_none()
    if served_card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found",
        )

    canonical_card = served_card
    if served_card.variant_of_card_id is not None:
        canonical_result = await db.execute(
            select(Card)
            .options(selectinload(Card.topic))
            .where(Card.id == served_card.variant_of_card_id)
        )
        loaded_canonical = canonical_result.scalar_one_or_none()
        if loaded_canonical is not None:
            canonical_card = loaded_canonical

    # Load existing review state for this user + canonical card, if any.
    state_result = await db.execute(
        select(ReviewState).where(
            ReviewState.user_id == current_user.id,
            ReviewState.card_id == canonical_card.id,
        )
    )
    review_state = state_result.scalar_one_or_none()

    # RAG-style context from served card chunk if available.
    explanation = None
    chunks_by_id = getattr(request.app.state, "chunks_by_id", {}) or {}
    if served_card.source_chunk_id and served_card.source_chunk_id in chunks_by_id:
        chunk = chunks_by_id[served_card.source_chunk_id]
        text = getattr(chunk, "text", "")
        if text:
            max_len = 600
            explanation = text[:max_len] + ("..." if len(text) > max_len else "")

    subject = canonical_card.topic.name if canonical_card.topic else None  # type: ignore[union-attr]
    grade = grade_answer(
        question=served_card.question,
        reference_answer=served_card.answer,
        user_answer=payload.user_answer,
        subject=subject,
        context_excerpt=explanation,
    )

    updated_state, attempt = svc.record_attempt(
        user_id=current_user.id,
        card=canonical_card,
        review_state=review_state,
        quality=grade.score_0_5,
        served_card_id=served_card.id,
        response_time_ms=payload.response_time_ms,
    )

    if review_state is None:
        db.add(updated_state)
    db.add(attempt)
    await db.commit()
    await db.refresh(updated_state)

    topic_cards_result = await db.execute(
        select(Card)
        .options(selectinload(Card.topic))
        .where(Card.topic_id == canonical_card.topic_id)
    )
    topic_cards = topic_cards_result.scalars().unique().all()
    await _refresh_swot_snapshot(
        db=db,
        user_id=current_user.id,
        cards=topic_cards,
    )

    return QuizAnswerResponse(
        answer=served_card.answer,
        explanation=explanation,
        source_chunk_id=served_card.source_chunk_id,
        model_score=grade.score_0_5,
        verdict=grade.verdict,
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
    card_result = await db.execute(
        select(Card).join(Topic).options(selectinload(Card.topic))
    )
    cards = card_result.scalars().unique().all()

    await _refresh_swot_snapshot(
        db=db,
        user_id=current_user.id,
        cards=cards,
    )

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


@router.post("/sessions/start", response_model=QuizSessionStartResponse)
async def start_quiz_session(
    payload: QuizSessionStartRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: Request,
) -> QuizSessionStartResponse:
    session_service = QuizSessionService(
        chunks_by_id=getattr(request.app.state, "chunks_by_id", {}) or {}
    )
    state = await session_service.start_session(
        db=db,
        user_id=current_user.id,
        limit=payload.limit,
        topics=payload.topics,
        subject=payload.subject,
    )
    _quiz_sessions_store(request)[state.session_id] = state

    current_card = await session_service.get_current_presented_card(
        db=db,
        state=state,
    )
    return QuizSessionStartResponse(
        session_id=state.session_id,
        current_card=_to_quiz_card(current_card) if current_card else None,
        progress=_progress(state),
        path=_to_path_nodes(state.path_nodes),
    )


@router.post("/sessions/{session_id}/answer", response_model=QuizSessionAnswerResponse)
async def answer_quiz_session(
    session_id: str,
    payload: QuizSessionAnswerRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: Request,
) -> QuizSessionAnswerResponse:
    store = _quiz_sessions_store(request)
    state = store.get(session_id)
    if state is None or state.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session_service = QuizSessionService(
        chunks_by_id=getattr(request.app.state, "chunks_by_id", {}) or {}
    )
    try:
        outcome = await session_service.submit_current_answer(
            db=db,
            state=state,
            card_id=payload.card_id,
            user_answer=payload.user_answer,
            response_time_ms=payload.response_time_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return QuizSessionAnswerResponse(
        answer=outcome.answer,
        explanation=outcome.explanation,
        source_chunk_id=outcome.source_chunk_id,
        model_score=outcome.grade.score_0_5,
        verdict=outcome.grade.verdict,
        next_due_at=(
            outcome.updated_state.due_at.isoformat()
            if outcome.updated_state.due_at
            else None
        ),
        interval_days=outcome.updated_state.interval_days,
        next_card=_to_quiz_card(outcome.next_card) if outcome.next_card else None,
        progress=_progress(state),
    )


@router.post("/sessions/{session_id}/finish", response_model=QuizSessionFinishResponse)
async def finish_quiz_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    request: Request,
) -> QuizSessionFinishResponse:
    store = _quiz_sessions_store(request)
    state = store.get(session_id)
    if state is None or state.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    store.pop(session_id, None)
    return QuizSessionFinishResponse(status="finished", session_id=session_id)


