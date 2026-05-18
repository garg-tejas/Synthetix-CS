"""Async Clerk session token verification using Clerk's JWKS endpoint."""

from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from jose import JWTError, jwt

CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY")
CLERK_JWKS_URL = os.environ.get("CLERK_JWKS_URL", "https://api.clerk.com/v1/jwks")


async def verify_clerk_session_token(token: str) -> Dict[str, Any]:
    """
    Verify a Clerk session JWT by fetching JWKS from Clerk and decoding
    the token with the appropriate public key.

    Returns the token payload (including 'sub' which is the Clerk user_id).

    Raises ValueError if CLERK_SECRET_KEY is not configured.
    Raises JWTError if the token is invalid or expired.
    """
    if not CLERK_SECRET_KEY:
        raise ValueError(
            "CLERK_SECRET_KEY environment variable is required to verify Clerk tokens."
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            CLERK_JWKS_URL,
            headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
        )
        resp.raise_for_status()
        jwks_data = resp.json()

    # Find the key that matches the token's kid
    unverified = jwt.get_unverified_header(token)
    kid = unverified.get("kid")
    if not kid:
        raise JWTError("Token missing 'kid' header")

    signing_key = None
    for key in jwks_data.get("keys", []):
        if key.get("kid") == kid:
            signing_key = key
            break

    if signing_key is None:
        raise JWTError(f"No matching JWKS key found for kid={kid}")

    # jose's jwt.decode can accept a dict key directly for RS256
    payload = jwt.decode(
        token,
        signing_key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    return payload
