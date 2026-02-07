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
    user_answer: str = Field(
        ...,
        description="The user's free-text answer to the question",
    )
    quality: Optional[int] = Field(
        default=None,
        ge=0,
        le=5,
        description="Optional self-assessed quality score from 0 (complete blackout) to 5 (perfect recall)",
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
    model_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=5,
        description="Model-graded score from 0 to 5",
    )
    verdict: Optional[str] = Field(
        default=None,
        description="High-level grading verdict: correct, partially_correct, or incorrect",
    )
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


class LearningPathNode(BaseModel):
    subject: str
    topic_key: str
    display_name: str
    mastery_score: float
    swot_bucket: str
    priority_score: float


class SessionProgress(BaseModel):
    current_index: int = Field(
        ...,
        ge=0,
        description="Zero-based index of the current step in this session",
    )
    total: int = Field(..., ge=0, description="Total cards in the session queue")
    completed: bool


class QuizSessionStartRequest(BaseModel):
    topics: Optional[List[str]] = Field(
        default=None,
        description="Optional list of topic names to scope this session",
    )
    subject: Optional[str] = Field(
        default=None,
        description="Optional subject alias (os/cn/dbms)",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of cards to include in the session queue",
    )


class QuizSessionStartResponse(BaseModel):
    session_id: str
    current_card: Optional[QuizCard] = None
    progress: SessionProgress
    path: List[LearningPathNode] = Field(default_factory=list)


class QuizSessionAnswerRequest(BaseModel):
    card_id: int
    user_answer: str
    response_time_ms: Optional[int] = Field(default=None, ge=0)


class QuizSessionAnswerResponse(BaseModel):
    answer: str
    explanation: Optional[str] = None
    source_chunk_id: Optional[str] = None
    model_score: Optional[int] = Field(default=None, ge=0, le=5)
    verdict: Optional[str] = None
    next_due_at: Optional[str] = None
    interval_days: Optional[int] = None
    next_card: Optional[QuizCard] = None
    progress: SessionProgress


class QuizSessionFinishResponse(BaseModel):
    status: str
    session_id: str

