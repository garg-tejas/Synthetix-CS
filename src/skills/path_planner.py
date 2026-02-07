from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import TopicPrerequisite, TopicTaxonomyNode, UserTopicMastery, UserTopicSWOT


@dataclass
class PathNode:
    subject: str
    topic_key: str
    display_name: str
    mastery_score: float
    swot_bucket: str
    priority_score: float
    prerequisite_topic_keys: list[str] = field(default_factory=list)


def compute_priority_score(*, mastery_score: float, swot_bucket: str) -> float:
    deficit = max(0.0, 100.0 - mastery_score)
    bucket_bonus = {
        "weakness": 28.0,
        "threat": 22.0,
        "opportunity": 14.0,
        "strength": 4.0,
    }.get(swot_bucket, 12.0)
    return deficit + bucket_bonus


class LearningPathPlanner:
    def order_nodes(
        self,
        *,
        nodes: Dict[Tuple[str, str], PathNode],
        prerequisites: Iterable[Tuple[Tuple[str, str], Tuple[str, str]]],
    ) -> List[PathNode]:
        if not nodes:
            return []

        outgoing: Dict[Tuple[str, str], set[Tuple[str, str]]] = {k: set() for k in nodes.keys()}
        indegree: Dict[Tuple[str, str], int] = {k: 0 for k in nodes.keys()}

        for topic, prereq in prerequisites:
            if topic not in nodes or prereq not in nodes:
                continue
            if topic in outgoing[prereq]:
                continue
            outgoing[prereq].add(topic)
            indegree[topic] += 1

        ready = [key for key, deg in indegree.items() if deg == 0]
        ordered_keys: List[Tuple[str, str]] = []

        while ready:
            ready.sort(
                key=lambda key: (
                    -nodes[key].priority_score,
                    nodes[key].topic_key,
                )
            )
            current = ready.pop(0)
            ordered_keys.append(current)
            for nxt in sorted(outgoing[current]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)

        if len(ordered_keys) < len(nodes):
            # If cycles exist, append remaining by priority.
            remaining = [key for key in nodes.keys() if key not in ordered_keys]
            remaining.sort(
                key=lambda key: (
                    -nodes[key].priority_score,
                    nodes[key].topic_key,
                )
            )
            ordered_keys.extend(remaining)

        return [nodes[key] for key in ordered_keys]

    async def build_path(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        subject: Optional[str] = None,
        topic_keys: Optional[Iterable[str]] = None,
    ) -> List[PathNode]:
        mastery_stmt = select(UserTopicMastery).where(UserTopicMastery.user_id == user_id)
        swot_stmt = select(UserTopicSWOT).where(UserTopicSWOT.user_id == user_id)
        taxonomy_stmt = select(TopicTaxonomyNode)
        prereq_stmt = select(TopicPrerequisite)

        if subject:
            mastery_stmt = mastery_stmt.where(UserTopicMastery.subject == subject)
            swot_stmt = swot_stmt.where(UserTopicSWOT.subject == subject)
            taxonomy_stmt = taxonomy_stmt.where(TopicTaxonomyNode.subject == subject)
            prereq_stmt = prereq_stmt.where(TopicPrerequisite.subject == subject)

        keys_filter = set(topic_keys) if topic_keys else None
        if keys_filter:
            keys_list = sorted(keys_filter)
            mastery_stmt = mastery_stmt.where(UserTopicMastery.topic_key.in_(keys_list))
            swot_stmt = swot_stmt.where(UserTopicSWOT.topic_key.in_(keys_list))
            taxonomy_stmt = taxonomy_stmt.where(TopicTaxonomyNode.topic_key.in_(keys_list))
            prereq_stmt = prereq_stmt.where(
                and_(
                    TopicPrerequisite.topic_key.in_(keys_list),
                    TopicPrerequisite.prerequisite_key.in_(keys_list),
                )
            )

        mastery_rows = (await db.execute(mastery_stmt)).scalars().all()
        swot_rows = (await db.execute(swot_stmt)).scalars().all()
        taxonomy_rows = (await db.execute(taxonomy_stmt)).scalars().all()
        prereq_rows = (await db.execute(prereq_stmt)).scalars().all()

        mastery_by_key = {(row.subject, row.topic_key): row for row in mastery_rows}
        swot_by_key = {(row.subject, row.topic_key): row for row in swot_rows}
        taxonomy_by_key = {(row.subject, row.topic_key): row for row in taxonomy_rows}

        all_keys = set(mastery_by_key.keys()) | set(swot_by_key.keys()) | set(taxonomy_by_key.keys())
        if not all_keys:
            return []

        nodes: Dict[Tuple[str, str], PathNode] = {}
        for key in all_keys:
            subject_key, topic_key = key
            mastery = mastery_by_key.get(key)
            swot = swot_by_key.get(key)
            taxonomy = taxonomy_by_key.get(key)
            mastery_score = float(mastery.mastery_score) if mastery is not None else 0.0
            swot_bucket = swot.primary_bucket if swot is not None else "opportunity"
            display_name = (
                taxonomy.display_name
                if taxonomy is not None
                else topic_key.split(":", 1)[-1].replace("-", " ").title()
            )
            nodes[key] = PathNode(
                subject=subject_key,
                topic_key=topic_key,
                display_name=display_name,
                mastery_score=mastery_score,
                swot_bucket=swot_bucket,
                priority_score=compute_priority_score(
                    mastery_score=mastery_score,
                    swot_bucket=swot_bucket,
                ),
            )

        prerequisites: List[Tuple[Tuple[str, str], Tuple[str, str]]] = []
        prereq_keys_by_topic: Dict[Tuple[str, str], set[str]] = {}
        for edge in prereq_rows:
            topic = (edge.subject, edge.topic_key)
            prerequisite = (edge.subject, edge.prerequisite_key)
            prerequisites.append((topic, prerequisite))
            if topic not in nodes or prerequisite not in nodes:
                continue
            prereq_keys_by_topic.setdefault(topic, set()).add(edge.prerequisite_key)

        for key, node in nodes.items():
            node.prerequisite_topic_keys = sorted(prereq_keys_by_topic.get(key, set()))

        return self.order_nodes(nodes=nodes, prerequisites=prerequisites)
