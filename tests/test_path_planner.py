from __future__ import annotations

from src.skills.path_planner import LearningPathPlanner, PathNode


def _node(
    *,
    subject: str,
    topic_key: str,
    mastery_score: float,
    swot_bucket: str,
    priority_score: float,
) -> PathNode:
    return PathNode(
        subject=subject,
        topic_key=topic_key,
        display_name=topic_key,
        mastery_score=mastery_score,
        swot_bucket=swot_bucket,
        priority_score=priority_score,
    )


def test_order_nodes_respects_prerequisites_even_if_priority_lower():
    planner = LearningPathPlanner()
    os_process = _node(
        subject="os",
        topic_key="os:process",
        mastery_score=80.0,
        swot_bucket="strength",
        priority_score=20.0,
    )
    os_deadlock = _node(
        subject="os",
        topic_key="os:deadlock",
        mastery_score=20.0,
        swot_bucket="weakness",
        priority_score=95.0,
    )
    nodes = {
        ("os", "os:process"): os_process,
        ("os", "os:deadlock"): os_deadlock,
    }
    # deadlock depends on process
    ordered = planner.order_nodes(
        nodes=nodes,
        prerequisites=[(("os", "os:deadlock"), ("os", "os:process"))],
    )
    assert [n.topic_key for n in ordered] == ["os:process", "os:deadlock"]


def test_order_nodes_uses_priority_when_no_prerequisites():
    planner = LearningPathPlanner()
    a = _node(
        subject="dbms",
        topic_key="dbms:index",
        mastery_score=30.0,
        swot_bucket="weakness",
        priority_score=85.0,
    )
    b = _node(
        subject="dbms",
        topic_key="dbms:sql",
        mastery_score=70.0,
        swot_bucket="opportunity",
        priority_score=45.0,
    )
    ordered = planner.order_nodes(
        nodes={
            ("dbms", "dbms:index"): a,
            ("dbms", "dbms:sql"): b,
        },
        prerequisites=[],
    )
    assert [n.topic_key for n in ordered] == ["dbms:index", "dbms:sql"]
