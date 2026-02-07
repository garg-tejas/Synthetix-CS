from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Card, ReviewAttempt
from src.llm import create_client


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _extract_json_object(raw: str) -> Optional[dict[str, Any]]:
    if not raw or not raw.strip():
        return None

    text = raw.strip()
    candidates = [text]
    fenced = _JSON_FENCE_RE.search(text)
    if fenced:
        candidates.insert(0, fenced.group(1))
    if not text.startswith("{"):
        generic = re.search(r"\{.*\}", text, re.DOTALL)
        if generic:
            candidates.append(generic.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _valid_payload(payload: dict[str, Any], canonical: Card) -> bool:
    query = str(payload.get("query") or "").strip()
    answer = str(payload.get("answer") or "").strip()
    qtype = str(payload.get("question_type") or "").strip().lower()
    difficulty = str(payload.get("difficulty") or "").strip().lower()
    if not query or not answer:
        return False
    if query.lower() == canonical.question.strip().lower():
        return False
    if qtype not in {"definition", "procedural", "comparative", "factual"}:
        return False
    if difficulty not in {"easy", "medium", "hard"}:
        return False
    return True


class VariantGenerator:
    def __init__(self, *, chunks_by_id: Optional[dict[str, Any]] = None) -> None:
        self.chunks_by_id = chunks_by_id or {}

    async def select_or_create_variant(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        canonical_card: Card,
        now: Optional[dt.datetime] = None,
    ) -> Card:
        now = now or dt.datetime.now(dt.timezone.utc)
        variants_result = await db.execute(
            select(Card)
            .where(Card.variant_of_card_id == canonical_card.id)
            .order_by(Card.created_at.desc(), Card.id.desc())
        )
        variants = variants_result.scalars().all()
        if variants:
            recent_result = await db.execute(
                select(ReviewAttempt.served_card_id, ReviewAttempt.attempted_at)
                .where(
                    ReviewAttempt.user_id == user_id,
                    ReviewAttempt.card_id == canonical_card.id,
                    ReviewAttempt.served_card_id.is_not(None),
                )
                .order_by(ReviewAttempt.attempted_at.desc())
                .limit(30)
            )
            last_seen: dict[int, dt.datetime] = {}
            for served_id, attempted_at in recent_result.all():
                if served_id is None:
                    continue
                if served_id not in last_seen:
                    last_seen[served_id] = attempted_at

            # Prefer variants with no recent usage first.
            unseen = [variant for variant in variants if variant.id not in last_seen]
            if unseen:
                chosen = unseen[0]
            else:
                chosen = sorted(
                    variants,
                    key=lambda variant: last_seen.get(variant.id, dt.datetime.min.replace(tzinfo=dt.timezone.utc)),
                )[0]
            if chosen.topic is None and canonical_card.topic is not None:  # type: ignore[union-attr]
                chosen.topic = canonical_card.topic  # type: ignore[assignment]
            return chosen

        payload = self._generate_variant_payload(canonical_card)
        if payload is None:
            return canonical_card

        variant = Card(
            topic_id=canonical_card.topic_id,
            question=payload["query"],
            answer=payload["answer"],
            difficulty=payload["difficulty"],
            question_type=payload["question_type"],
            source_chunk_id=canonical_card.source_chunk_id,
            tags=canonical_card.tags,
            topic_key=canonical_card.topic_key,
            variant_of_card_id=canonical_card.id,
            generation_origin="runtime_variant",
            provenance_json={
                "source": "runtime_variant_generation",
                "canonical_card_id": canonical_card.id,
                "generated_at": now.isoformat(),
            },
        )
        db.add(variant)
        await db.commit()
        await db.refresh(variant)
        if canonical_card.topic is not None:  # type: ignore[union-attr]
            variant.topic = canonical_card.topic  # type: ignore[assignment]
        return variant

    def _generate_variant_payload(self, canonical: Card) -> Optional[dict[str, str]]:
        context_text = ""
        if canonical.source_chunk_id and canonical.source_chunk_id in self.chunks_by_id:
            chunk = self.chunks_by_id[canonical.source_chunk_id]
            context_text = str(getattr(chunk, "text", "") or "")
        context_excerpt = context_text[:1200] if context_text else ""

        prompt = f"""Generate one similar technical interview question.
Constraints:
- Keep concept aligned with canonical.
- Do not repeat the exact same question wording.
- Keep answer grounded in source context.
- Return JSON only.

Canonical question:
{canonical.question}

Canonical answer:
{canonical.answer}

Source context:
{context_excerpt}

Output format:
{{
  "query": "...",
  "answer": "...",
  "question_type": "definition|procedural|comparative|factual",
  "difficulty": "easy|medium|hard"
}}
"""
        try:
            client = create_client()
            raw = client.generate_single(prompt, max_tokens=500, temperature=0.3)
        except Exception:
            return None

        payload = _extract_json_object(raw)
        if not payload or not _valid_payload(payload, canonical):
            return None
        return {
            "query": str(payload["query"]).strip(),
            "answer": str(payload["answer"]).strip(),
            "question_type": str(payload["question_type"]).strip().lower(),
            "difficulty": str(payload["difficulty"]).strip().lower(),
        }
