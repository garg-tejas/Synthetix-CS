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


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_quiz_endpoints_require_auth(client: TestClient):
    # Without auth, quiz endpoints should reject the request.
    r_topics = client.get("/api/quiz/topics")
    r_stats = client.get("/api/quiz/stats")
    r_session_start = client.post("/api/quiz/sessions/start", json={})
    r_session_answer = client.post(
        "/api/quiz/sessions/fake-session/answer",
        json={"card_id": 1, "user_answer": "test"},
    )
    r_session_finish = client.post("/api/quiz/sessions/fake-session/finish")

    assert r_topics.status_code == 401
    assert r_stats.status_code == 401
    assert r_session_start.status_code == 401
    assert r_session_answer.status_code == 401
    assert r_session_finish.status_code == 401


def test_quiz_topics_and_stats_authenticated(client: TestClient):
    token = _signup_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Topics
    r_topics = client.get("/api/quiz/topics", headers=headers)
    assert r_topics.status_code == 200
    topics = r_topics.json()
    assert isinstance(topics, list)

    # Stats
    r_stats = client.get("/api/quiz/stats", headers=headers)
    assert r_stats.status_code == 200
    stats = r_stats.json()
    assert "topics" in stats
    assert isinstance(stats["topics"], list)


def test_quiz_session_start_and_finish_authenticated(client: TestClient):
    token = _signup_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    r_start = client.post(
        "/api/quiz/sessions/start",
        json={"limit": 5},
        headers=headers,
    )
    assert r_start.status_code == 200
    start_data = r_start.json()
    assert "session_id" in start_data
    assert "current_card" in start_data
    assert "progress" in start_data
    assert "path" in start_data
    assert isinstance(start_data["path"], list)
    if start_data["path"]:
        assert "prerequisite_topic_keys" in start_data["path"][0]
        assert isinstance(start_data["path"][0]["prerequisite_topic_keys"], list)
    assert start_data["progress"]["total"] >= 0

    session_id = start_data["session_id"]

    r_answer = client.post(
        f"/api/quiz/sessions/{session_id}/answer",
        json={"card_id": 999999, "user_answer": "attempt"},
        headers=headers,
    )
    # If no cards exist, session is complete; otherwise invalid current card.
    if r_answer.status_code == 200:
        answer_data = r_answer.json()
        assert "answer" in answer_data
        assert "show_source_context" in answer_data
        assert "should_remediate" in answer_data
        assert "concept_summary" in answer_data
        assert "where_you_missed" in answer_data
        assert isinstance(answer_data["where_you_missed"], list)
    else:
        assert r_answer.status_code in (400, 404)

    r_finish = client.post(
        f"/api/quiz/sessions/{session_id}/finish",
        headers=headers,
    )
    assert r_finish.status_code == 200
    finish_data = r_finish.json()
    assert finish_data["status"] == "finished"
    assert finish_data["session_id"] == session_id
