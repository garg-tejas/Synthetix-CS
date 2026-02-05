"""
Integration tests for quiz-related FastAPI endpoints.

These tests assume:
- The database is reachable (as configured in DATABASE_URL).
- Core tables have been created via Alembic.
They do not depend on any pre-seeded Card/Topic data; they focus on
auth wiring, status codes, and basic response shapes.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.api.main import app


def _signup_and_get_token(client: TestClient) -> str:
    # Use a unique email/username per run to avoid conflicts.
    import uuid

    suffix = uuid.uuid4().hex[:8]
    email = f"quiz_{suffix}@example.com"
    username = f"quiz_{suffix}"
    password = "Str0ngP@ssw0rd!"

    r = client.post(
        "/auth/signup",
        json={"email": email, "username": username, "password": password},
    )
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    return data["access_token"]


def test_quiz_endpoints_require_auth():
    client = TestClient(app)
    # Without auth, quiz endpoints should reject the request.
    r_topics = client.get("/api/quiz/topics")
    r_next = client.post("/api/quiz/next", json={})
    r_stats = client.get("/api/quiz/stats")
    r_answer = client.post(
        "/api/quiz/answer",
        json={"card_id": 1, "user_answer": "test answer", "quality": 3},
    )

    assert r_topics.status_code == 401
    assert r_next.status_code == 401
    assert r_stats.status_code == 401
    assert r_answer.status_code == 401


def test_quiz_topics_next_and_stats_authenticated():
    client = TestClient(app)
    token = _signup_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Topics
    r_topics = client.get("/api/quiz/topics", headers=headers)
    assert r_topics.status_code == 200
    topics = r_topics.json()
    assert isinstance(topics, list)

    # Next
    r_next = client.post("/api/quiz/next", json={}, headers=headers)
    assert r_next.status_code == 200
    next_data = r_next.json()
    assert "cards" in next_data
    assert "due_count" in next_data
    assert "new_count" in next_data

    # Stats
    r_stats = client.get("/api/quiz/stats", headers=headers)
    assert r_stats.status_code == 200
    stats = r_stats.json()
    assert "topics" in stats
    assert isinstance(stats["topics"], list)


def test_quiz_answer_nonexistent_card_returns_404():
    client = TestClient(app)
    token = _signup_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/api/quiz/answer",
        json={"card_id": 999999, "user_answer": "test answer", "quality": 3},
        headers=headers,
    )
    assert r.status_code in (404, 400)
    # If 404, we expect our "Card not found" message.
    if r.status_code == 404:
        assert r.json().get("detail") == "Card not found"

