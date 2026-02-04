"""
Unit tests for auth utilities and dependencies (no real DB or HTTP).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.auth.dependencies import get_current_user
from src.auth.service import (
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from src.db.models import User


def test_password_hash_and_verify_roundtrip():
    password = "Str0ngP@ssw0rd!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_create_and_decode_tokens():
    user_id = 123
    tokens = create_token_pair(user_id)
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    access_payload = decode_token(tokens["access_token"])
    refresh_payload = decode_token(tokens["refresh_token"])

    assert access_payload["sub"] == str(user_id)
    assert access_payload["type"] == "access"
    assert refresh_payload["sub"] == str(user_id)
    assert refresh_payload["type"] == "refresh"


class _FakeResult:
    def __init__(self, obj: Any | None):
        self._obj = obj

    def scalar_one_or_none(self) -> Any | None:
        return self._obj


class _FakeSession:
    def __init__(self, user: User | None):
        self._user = user

    async def execute(self, _query: Any) -> _FakeResult:
        return _FakeResult(self._user)


@pytest.mark.anyio
async def test_get_current_user_with_valid_token():
    # Prepare a fake user and DB session
    user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("password"),
        is_active=True,
    )
    db = _FakeSession(user)

    tokens = create_token_pair(user.id)
    access_token = tokens["access_token"]

    current = await get_current_user(token=access_token, db=db)  # type: ignore[arg-type]
    assert current.id == user.id
    assert current.email == user.email
    assert current.username == user.username

