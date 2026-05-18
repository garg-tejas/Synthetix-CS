from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import sqlite

from src.db.models import Card, Topic
from src.skills.session_service import QuizSessionService


def test_normalize_scope_values_lowercases_and_drops_blanks():
    values = QuizSessionService._normalize_scope_values(
        [" os ", "", "OS:Deadlock", "  ", "dbms:indexes"]
    )

    assert values == ["os", "os:deadlock", "dbms:indexes"]


def test_session_scope_query_supports_subject_names_and_topic_keys():
    normalized_topics = QuizSessionService._normalize_scope_values(
        ["os", "os:deadlock"]
    )
    query = (
        select(Card)
        .join(Topic)
        .where(Topic.name.in_(normalized_topics) | Card.topic_key.in_(normalized_topics))
    )

    compiled = str(
        query.compile(
            dialect=sqlite.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "topics.name IN ('os', 'os:deadlock')" in compiled
    assert "cards.topic_key IN ('os', 'os:deadlock')" in compiled
