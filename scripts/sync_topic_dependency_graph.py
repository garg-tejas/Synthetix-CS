"""
Sync validated topic dependency graph artifacts into database tables.

Usage:
  uv run python -m scripts.sync_topic_dependency_graph
  uv run python -m scripts.sync_topic_dependency_graph --subject os --replace-subject
  uv run python -m scripts.sync_topic_dependency_graph --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import and_, delete, select

from src.db.models import TopicPrerequisite, TopicTaxonomyNode
from src.db.session import AsyncSessionLocal


_DEFAULT_INPUT = Path("eval/generation/output/topic_graph.validated.json")


def _normalize_subject(value: str) -> str:
    return value.strip().lower()


def _load_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("graph payload must be a JSON object")
    return raw


def _subject_blocks(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    subjects = payload.get("subjects")
    if isinstance(subjects, list):
        return [row for row in subjects if isinstance(row, dict)]

    # Accept single-subject file shape:
    # {"subject": "...", "topics": [...], "validated_edges": [...]}
    if "subject" in payload:
        return [payload]
    return []


def _topic_rows(block: Dict[str, Any], *, subject: str) -> List[Tuple[str, str]]:
    topics = block.get("topics")
    if not isinstance(topics, list):
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in topics:
        if not isinstance(row, dict):
            continue
        topic_key = str(row.get("topic_key") or "").strip().lower()
        if not topic_key or topic_key in seen:
            continue
        seen.add(topic_key)
        display_name = str(row.get("display_name") or "").strip()
        if not display_name:
            display_name = topic_key.split(":", 1)[-1].replace("-", " ").replace("_", " ").title()
        out.append((topic_key, display_name))
    return out


def _edge_rows(
    block: Dict[str, Any],
    *,
    subject: str,
    allowed_topic_keys: set[str],
) -> List[Tuple[str, str, float, str]]:
    edges = block.get("validated_edges")
    if not isinstance(edges, list):
        return []
    out: list[tuple[str, str, float, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in edges:
        if not isinstance(row, dict):
            continue
        topic_key = str(row.get("topic_key") or "").strip().lower()
        prerequisite_key = str(row.get("prerequisite_key") or "").strip().lower()
        if (
            not topic_key
            or not prerequisite_key
            or topic_key == prerequisite_key
            or topic_key not in allowed_topic_keys
            or prerequisite_key not in allowed_topic_keys
        ):
            continue
        pair = (topic_key, prerequisite_key)
        if pair in seen:
            continue
        seen.add(pair)
        try:
            confidence = float(row.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        rationale = str(row.get("rationale") or "").strip()
        out.append((topic_key, prerequisite_key, confidence, rationale))
    return out


async def _apply_for_subject(
    *,
    subject: str,
    topics: List[Tuple[str, str]],
    edges: List[Tuple[str, str, float, str]],
    replace_subject: bool,
    dry_run: bool,
) -> dict[str, int]:
    stats = {
        "topics_inserted": 0,
        "topics_updated": 0,
        "edges_inserted": 0,
        "edges_updated": 0,
        "topics_deleted": 0,
        "edges_deleted": 0,
    }

    async with AsyncSessionLocal() as session:
        if replace_subject:
            if dry_run:
                existing_topics_count = (
                    await session.execute(
                        select(TopicTaxonomyNode).where(TopicTaxonomyNode.subject == subject)
                    )
                ).scalars().all()
                existing_edges_count = (
                    await session.execute(
                        select(TopicPrerequisite).where(TopicPrerequisite.subject == subject)
                    )
                ).scalars().all()
                stats["topics_deleted"] = len(existing_topics_count)
                stats["edges_deleted"] = len(existing_edges_count)
            else:
                edges_deleted = await session.execute(
                    delete(TopicPrerequisite).where(TopicPrerequisite.subject == subject)
                )
                topics_deleted = await session.execute(
                    delete(TopicTaxonomyNode).where(TopicTaxonomyNode.subject == subject)
                )
                stats["edges_deleted"] = int(edges_deleted.rowcount or 0)
                stats["topics_deleted"] = int(topics_deleted.rowcount or 0)

        existing_topics = (
            await session.execute(
                select(TopicTaxonomyNode).where(TopicTaxonomyNode.subject == subject)
            )
        ).scalars().all()
        topic_map = {row.topic_key: row for row in existing_topics}

        for topic_key, display_name in topics:
            row = topic_map.get(topic_key)
            if row is None:
                if not dry_run:
                    session.add(
                        TopicTaxonomyNode(
                            subject=subject,
                            topic_key=topic_key,
                            display_name=display_name,
                            parent_topic_key=None,
                            source="llm_v1",
                            metadata_json={"generated_by": "topic_graph_builder"},
                        )
                    )
                stats["topics_inserted"] += 1
            else:
                if (
                    row.display_name != display_name
                    or row.source != "llm_v1"
                    or (row.metadata_json or {}).get("generated_by") != "topic_graph_builder"
                ):
                    if not dry_run:
                        row.display_name = display_name
                        row.source = "llm_v1"
                        row.metadata_json = {"generated_by": "topic_graph_builder"}
                    stats["topics_updated"] += 1

        existing_edges = (
            await session.execute(
                select(TopicPrerequisite).where(TopicPrerequisite.subject == subject)
            )
        ).scalars().all()
        edge_map = {(row.topic_key, row.prerequisite_key): row for row in existing_edges}

        for topic_key, prerequisite_key, confidence, rationale in edges:
            key = (topic_key, prerequisite_key)
            row = edge_map.get(key)
            evidence = {"rationale": rationale, "confidence": confidence}
            if row is None:
                if not dry_run:
                    session.add(
                        TopicPrerequisite(
                            subject=subject,
                            topic_key=topic_key,
                            prerequisite_key=prerequisite_key,
                            weight=confidence,
                            source="llm_v1",
                            evidence_json=evidence,
                        )
                    )
                stats["edges_inserted"] += 1
            else:
                if (
                    abs(float(row.weight) - confidence) > 1e-9
                    or row.source != "llm_v1"
                    or (row.evidence_json or {}) != evidence
                ):
                    if not dry_run:
                        row.weight = confidence
                        row.source = "llm_v1"
                        row.evidence_json = evidence
                    stats["edges_updated"] += 1

        if not dry_run:
            await session.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync validated topic dependency graph into DB.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_DEFAULT_INPUT,
        help="Path to validated graph JSON (aggregate or single-subject format)",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help="Optional subject filter (os, dbms, cn)",
    )
    parser.add_argument(
        "--replace-subject",
        action="store_true",
        help="Delete and replace rows only for selected subject block(s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to DB",
    )
    args = parser.parse_args()

    payload = _load_payload(args.input)
    blocks = _subject_blocks(payload)
    if not blocks:
        raise ValueError("no subject blocks found in payload")

    requested_subject = _normalize_subject(args.subject) if args.subject else None

    async def _run() -> None:
        aggregate = {
            "topics_inserted": 0,
            "topics_updated": 0,
            "edges_inserted": 0,
            "edges_updated": 0,
            "topics_deleted": 0,
            "edges_deleted": 0,
        }
        for block in blocks:
            subject = _normalize_subject(str(block.get("subject") or ""))
            if not subject:
                continue
            if requested_subject and subject != requested_subject:
                continue

            topics = _topic_rows(block, subject=subject)
            topic_keys = {topic_key for topic_key, _display_name in topics}
            edges = _edge_rows(block, subject=subject, allowed_topic_keys=topic_keys)

            stats = await _apply_for_subject(
                subject=subject,
                topics=topics,
                edges=edges,
                replace_subject=args.replace_subject,
                dry_run=args.dry_run,
            )
            for key, value in stats.items():
                aggregate[key] += value
            print(
                "[subject=%s] topics=%s edges=%s | +topics:%s ~topics:%s +edges:%s ~edges:%s"
                % (
                    subject,
                    len(topics),
                    len(edges),
                    stats["topics_inserted"],
                    stats["topics_updated"],
                    stats["edges_inserted"],
                    stats["edges_updated"],
                )
            )
            if args.replace_subject:
                print(
                    "  deleted old rows -> topics:%s edges:%s"
                    % (stats["topics_deleted"], stats["edges_deleted"])
                )

        print("\nsummary:")
        for key, value in aggregate.items():
            print(f"- {key}: {value}")
        print(f"- dry_run: {args.dry_run}")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
