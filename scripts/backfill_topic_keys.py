"""
Backfill missing cards.topic_key values for existing rows.

Usage:
  python -m scripts.backfill_topic_keys
"""

from __future__ import annotations

import asyncio
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.models import Card
from src.db.session import AsyncSessionLocal


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str, *, max_len: int = 80) -> str:
    cleaned = _NON_ALNUM_RE.sub("-", text.strip().lower()).strip("-")
    if not cleaned:
        return "core"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip("-")


def infer_topic_key(card: Card) -> str:
    subject = card.topic.name.lower() if card.topic else "unknown"
    if card.topic_key:
        return card.topic_key.lower()
    if card.source_chunk_id:
        return f"{subject}:{_slugify(card.source_chunk_id)}"
    if card.question:
        return f"{subject}:{_slugify(card.question)}"
    return f"{subject}:core"


async def run() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Card)
            .options(selectinload(Card.topic))
            .where(Card.topic_key.is_(None))
        )
        cards = result.scalars().all()
        if not cards:
            print("No cards need topic_key backfill.")
            return

        for card in cards:
            card.topic_key = infer_topic_key(card)
            if not card.generation_origin:
                card.generation_origin = "seed"

        await session.commit()
        print(f"Backfilled topic_key for {len(cards)} cards.")


if __name__ == "__main__":
    asyncio.run(run())
