from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Card, ReviewAttempt
from src.llm import create_client

logger = logging.getLogger(__name__)

try:
    from eval.generation.interview_quality import assess_interview_quality
except ImportError:  # pragma: no cover – eval package may not be installed
    assess_interview_quality = None  # type: ignore[assignment,misc]


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
        self._pending_tasks: set[asyncio.Task] = set()

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
                    key=lambda variant: last_seen.get(
                        variant.id, dt.datetime.min.replace(tzinfo=dt.timezone.utc)
                    ),
                )[0]
            if chosen.topic is None and canonical_card.topic is not None:  # type: ignore[union-attr]
                chosen.topic = canonical_card.topic  # type: ignore[assignment]
            return chosen

        # No existing variants — return canonical immediately and generate in background.
        task = asyncio.create_task(
            self._generate_variant_background(
                canonical_card=canonical_card,
                topic_id=canonical_card.topic_id,
                source_chunk_id=canonical_card.source_chunk_id,
                tags=canonical_card.tags,
                topic_key=canonical_card.topic_key,
            )
        )
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        return canonical_card

    async def _generate_variant_background(
        self,
        *,
        canonical_card: Card,
        topic_id: int,
        source_chunk_id: Optional[str],
        tags: Optional[str],
        topic_key: Optional[str],
    ) -> None:
        """Background task: generate a variant and persist it."""
        try:
            payload = await asyncio.to_thread(
                self._generate_variant_payload, canonical_card
            )
            if payload is None:
                logger.debug(
                    "Background variant generation produced no valid payload for card %s",
                    canonical_card.id,
                )
                return

            # Quality gate: reject variants that fail structural quality checks.
            if assess_interview_quality is not None:
                assessment = assess_interview_quality(payload, min_score=50)
                if not assessment.keep:
                    logger.info(
                        "Background variant for card %s rejected by quality gate "
                        "(score=%d, reasons=%s)",
                        canonical_card.id,
                        assessment.score,
                        assessment.reasons,
                    )
                    return

            # Import session factory here to avoid circular imports
            from src.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as db:
                now = dt.datetime.now(dt.timezone.utc)
                variant = Card(
                    topic_id=topic_id,
                    question=payload["query"],
                    answer=payload["answer"],
                    difficulty=payload["difficulty"],
                    question_type=payload["question_type"],
                    source_chunk_id=source_chunk_id,
                    tags=tags,
                    topic_key=topic_key,
                    variant_of_card_id=canonical_card.id,
                    generation_origin="runtime_variant",
                    provenance_json={
                        "source": "runtime_variant_generation_background",
                        "canonical_card_id": canonical_card.id,
                        "generated_at": now.isoformat(),
                    },
                )
                db.add(variant)
                await db.commit()
                logger.info(
                    "Background variant created for card %s (variant id: %s)",
                    canonical_card.id,
                    variant.id,
                )
        except Exception:
            logger.exception(
                "Background variant generation failed for card %s", canonical_card.id
            )

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
