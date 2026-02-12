from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_active_user
from src.db.models import Card, ReviewAttempt, ReviewState, Topic, User
from src.db.session import get_db
from src.skills.path_planner import PathNode
from src.skills.quiz_service import QuizService
from src.skills.schemas import (
    LearningPathNode,
    QuizCard,
    QuizSessionAnswerRequest,
    QuizSessionAnswerResponse,
    QuizSessionFinishResponse,
    QuizSessionStartRequest,
    QuizSessionStartResponse,
    QuizStatsResponse,
    SessionProgress,
    TopicStats,
)
from src.skills.session_service import QuizSessionService, QuizSessionState
from src.skills.swot import refresh_user_swot


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
            prerequisite_topic_keys=node.prerequisite_topic_keys,
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


@router.get("/stats", response_model=QuizStatsResponse)
async def get_quiz_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> QuizStatsResponse:
    svc = QuizService()
    card_result = await db.execute(
        select(Card).join(Topic).options(selectinload(Card.topic))
    )
    cards = card_result.scalars().unique().all()

    await _refresh_swot_snapshot(
        db=db,
        user_id=current_user.id,
        cards=cards,
    )

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
        path_topics_ordered=payload.path_topics_ordered,
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
        show_source_context=bool(outcome.explanation),
        model_score=outcome.grade.score_0_5,
        verdict=outcome.grade.verdict,
        should_remediate=outcome.should_remediate,
        concept_summary=outcome.concept_summary,
        where_you_missed=outcome.where_you_missed,
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
