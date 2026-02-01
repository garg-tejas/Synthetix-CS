"""
Tests for Synthetix-CS FastAPI routes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health():
    """GET /api/health returns ok and chunks_loaded."""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "chunks_loaded" in data
    assert isinstance(data["chunks_loaded"], int)


def test_stats():
    """GET /api/stats returns active_conversations."""
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "active_conversations" in data
    assert isinstance(data["active_conversations"], int)


def test_search_requires_body():
    """POST /api/search without body returns 422."""
    r = client.post("/api/search", json={})
    assert r.status_code == 422


def test_search_with_query():
    """POST /api/search returns 200 with results or 503 if no chunks."""
    r = client.post("/api/search", json={"query": "deadlock", "top_k": 3})
    if r.status_code == 503:
        assert "detail" in r.json()
        return
    assert r.status_code == 200
    data = r.json()
    assert data["query"] == "deadlock"
    assert "results" in data
    assert isinstance(data["results"], list)


def test_chat_requires_body():
    """POST /api/chat without body returns 422."""
    r = client.post("/api/chat", json={})
    assert r.status_code == 422


def test_chat_with_query():
    """POST /api/chat returns 200 with answer or 503 if no chunks."""
    r = client.post("/api/chat", json={"query": "What is deadlock?"})
    if r.status_code == 503:
        assert "detail" in r.json()
        return
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "citations" in data
    assert "chunks_used" in data


def test_clear_conversation():
    """DELETE /api/conversation returns ok."""
    r = client.delete("/api/conversation?conversation_id=default")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "conversation_id": "default"}
