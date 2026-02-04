from __future__ import annotations

import datetime as dt
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=dt.datetime.utcnow,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    review_states: Mapped[List["ReviewState"]] = relationship(back_populates="user")
    review_attempts: Mapped[List["ReviewAttempt"]] = relationship(back_populates="user")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # os, cn, dbms for now
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cards: Mapped[List["Card"]] = relationship(back_populates="topic")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    difficulty: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    question_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Links back to the RAG chunk this card was generated from
    source_chunk_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # Optional comma-separated tags for future filtering
    tags: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=dt.datetime.utcnow,
        nullable=False,
    )

    topic: Mapped["Topic"] = relationship(back_populates="cards")
    review_states: Mapped[List["ReviewState"]] = relationship(back_populates="card")
    review_attempts: Mapped[List["ReviewAttempt"]] = relationship(back_populates="card")


class ReviewState(Base):
    __tablename__ = "review_states"
    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_review_state_user_card"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), nullable=False, index=True)

    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ease_factor: Mapped[float] = mapped_column(default=2.5, nullable=False)
    due_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lapses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship(back_populates="review_states")
    card: Mapped["Card"] = relationship(back_populates="review_states")


class ReviewAttempt(Base):
    __tablename__ = "review_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), nullable=False, index=True)

    attempted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=dt.datetime.utcnow,
        nullable=False,
    )
    quality: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-5
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="review_attempts")
    card: Mapped["Card"] = relationship(back_populates="review_attempts")

