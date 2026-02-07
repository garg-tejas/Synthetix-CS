from __future__ import annotations

from scripts.build_topic_dependency_graph import (
    PrereqEdge,
    _break_cycles,
    _filter_edges,
)


def _edge(
    topic: str,
    prerequisite: str,
    confidence: float,
    *,
    subject: str = "os",
) -> PrereqEdge:
    return PrereqEdge(
        subject=subject,
        topic_key=topic,
        prerequisite_key=prerequisite,
        confidence=confidence,
        rationale="test",
    )


def test_filter_edges_drops_unknown_and_low_confidence() -> None:
    edges = [
        _edge("os:deadlock", "os:process", 0.90),
        _edge("os:deadlock", "os:unknown", 0.90),
        _edge("os:sync", "os:process", 0.40),
    ]
    filtered = _filter_edges(
        edges=edges,
        allowed_topic_keys={"os:deadlock", "os:sync", "os:process"},
        min_confidence=0.70,
    )
    assert len(filtered) == 1
    assert filtered[0].topic_key == "os:deadlock"
    assert filtered[0].prerequisite_key == "os:process"


def test_break_cycles_removes_lowest_confidence_in_cycle() -> None:
    # Edges represent prereq -> topic direction as (topic, prerequisite)
    # A cycle:
    # process -> threads -> sync -> process
    edges = [
        _edge("os:threads", "os:process", 0.95),
        _edge("os:sync", "os:threads", 0.88),
        _edge("os:process", "os:sync", 0.35),
    ]

    acyclic, dropped = _break_cycles(edges)
    assert len(dropped) == 1
    assert dropped[0]["topic_key"] == "os:process"
    assert dropped[0]["prerequisite_key"] == "os:sync"
    assert len(acyclic) == 2


def test_break_cycles_keeps_acyclic_graph_intact() -> None:
    edges = [
        _edge("os:threads", "os:process", 0.95),
        _edge("os:sync", "os:threads", 0.88),
    ]
    acyclic, dropped = _break_cycles(edges)
    assert len(dropped) == 0
    assert len(acyclic) == 2
