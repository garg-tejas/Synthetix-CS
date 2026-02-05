from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class QuizCard(BaseModel):
    """Single quiz card to present to the user."""

    card_id: int
    topic: str
    question: str
    difficulty: Optional[str] = None
    question_type: Optional[str] = None


class QuizNextRequest(BaseModel):
    """Request body for fetching the next batch of quiz cards."""

    topics: Optional[List[str]] = Field(
        default=None,
        description="Optional list of topic names to filter by, e.g. ['os', 'cn']",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of cards to return",
    )


class QuizNextResponse(BaseModel):
    """Response body for /api/quiz/next."""

    cards: List[QuizCard] = Field(default_factory=list)
    due_count: int = Field(
        default=0,
        description="Number of due cards included in this batch",
    )
    new_count: int = Field(
        default=0,
        description="Number of new cards included in this batch",
    )


class QuizAnswerRequest(BaseModel):
    """Request body for submitting an answer rating."""

    card_id: int
    quality: int = Field(
        ...,
        ge=0,
        le=5,
        description="Self-assessed quality score from 0 (complete blackout) to 5 (perfect recall)",
    )
    response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional response time in milliseconds",
    )


class QuizAnswerResponse(BaseModel):
    """Response body for /api/quiz/answer."""

    answer: str
    explanation: Optional[str] = None
    source_chunk_id: Optional[str] = None
    next_due_at: Optional[str] = Field(
        default=None,
        description="ISO timestamp of the next scheduled review for this card",
    )
    interval_days: Optional[int] = Field(
        default=None,
        description="Scheduled interval in days after this review",
    )


class TopicStats(BaseModel):
    """Per-topic statistics for quiz progress."""

    topic: str
    total: int
    learned: int
    due_today: int
    overdue: int


class QuizStatsResponse(BaseModel):
    """Response body for /api/quiz/stats."""

    topics: List[TopicStats] = Field(default_factory=list)

