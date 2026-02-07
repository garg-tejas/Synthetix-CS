"""
Inspect learning-path dependency graph coverage in the database.

Usage:
  uv run python -m scripts.check_learning_path_graph
  uv run python -m scripts.check_learning_path_graph --subject os
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select

from src.db.models import TopicPrerequisite, TopicTaxonomyNode
from src.db.session import AsyncSessionLocal


async def run(*, subject: str | None = None, sample_edges: int = 10) -> None:
    async with AsyncSessionLocal() as session:
        taxonomy_stmt = select(TopicTaxonomyNode)
        prereq_stmt = select(TopicPrerequisite)
        if subject:
            taxonomy_stmt = taxonomy_stmt.where(TopicTaxonomyNode.subject == subject)
            prereq_stmt = prereq_stmt.where(TopicPrerequisite.subject == subject)

        taxonomy_count = (
            await session.execute(select(func.count()).select_from(taxonomy_stmt.subquery()))
        ).scalar_one()
        prereq_count = (
            await session.execute(select(func.count()).select_from(prereq_stmt.subquery()))
        ).scalar_one()

        print(f"subject={subject or 'all'}")
        print(f"topic_taxonomy_nodes={taxonomy_count}")
        print(f"topic_prerequisites={prereq_count}")

        if prereq_count > 0:
            rows = (
                await session.execute(
                    prereq_stmt.order_by(
                        TopicPrerequisite.subject,
                        TopicPrerequisite.topic_key,
                        TopicPrerequisite.prerequisite_key,
                    ).limit(sample_edges)
                )
            ).scalars().all()
            print("\nsample prerequisite edges:")
            for row in rows:
                print(
                    f"- [{row.subject}] {row.prerequisite_key} -> {row.topic_key} "
                    f"(weight={row.weight}, source={row.source})"
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect topic taxonomy and prerequisite graph availability.",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help="Optional subject filter (e.g., os, dbms, cn)",
    )
    parser.add_argument(
        "--sample-edges",
        type=int,
        default=10,
        help="Number of prerequisite edges to print when available",
    )
    args = parser.parse_args()
    asyncio.run(run(subject=args.subject, sample_edges=max(1, args.sample_edges)))


if __name__ == "__main__":
    main()
