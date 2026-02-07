from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class QuizCard(BaseModel):
    """Single quiz card to present to the user."""

    card_id: int
    canonical_card_id: Optional[int] = None
    is_variant: bool = False
    topic: str
    question: str
    difficulty: Optional[str] = None
    question_type: Optional[str] = None


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

