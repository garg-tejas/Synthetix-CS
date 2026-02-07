"""
Build canonical topic taxonomy + prerequisite graph from chunks using LLM-assisted extraction.

Pipeline:
1) Candidate extraction pass (topics + edge candidates)
2) Validation pass (edge confidence + rationale)
3) Rule filtering (self-loop, missing keys, confidence threshold)
4) Cycle breaking (drop lowest-confidence edge in each detected cycle)

Outputs:
- topic_graph.<subject>.candidates.json
- topic_graph.<subject>.validated.json
- topic_graph.validated.json (aggregate across subjects in this run)
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.llm import create_client
from src.rag.index import ChunkRecord, load_chunks


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_DEFAULT_OUTPUT_DIR = Path("eval/generation/output")
_DEFAULT_INPUT_CHUNKS = Path("data/chunks.jsonl")


@dataclasses.dataclass
class TopicNode:
    subject: str
    topic_key: str
    display_name: str
    source: str = "llm_v1"


@dataclasses.dataclass
class PrereqEdge:
    subject: str
    topic_key: str
    prerequisite_key: str
    confidence: float
    rationale: str
    source: str = "llm_v1"


def _slugify(text: str, *, max_len: int = 80) -> str:
    cleaned = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    if not cleaned:
        return "core"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rstrip("-")


def _to_topic_key(*, subject: str, raw_key: str, display_name: str) -> str:
    value = (raw_key or "").strip().lower()
    if value and ":" in value:
        head, tail = value.split(":", 1)
        if head == subject and tail:
            return f"{subject}:{_slugify(tail)}"
    if value:
        return f"{subject}:{_slugify(value)}"
    return f"{subject}:{_slugify(display_name)}"


def _extract_json_object(raw: str) -> Dict[str, Any] | None:
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


def _normalize_subject(value: str | None) -> str:
    return (value or "unknown").strip().lower()


def _infer_display_name(topic_key: str) -> str:
    tail = topic_key.split(":", 1)[-1]
    return tail.replace("-", " ").replace("_", " ").title()


def _build_subject_context(chunks: List[ChunkRecord], *, max_items: int = 120) -> str:
    items: list[str] = []
    for ch in chunks[:max_items]:
        header = (ch.header_path or "").strip()
        if not header:
            continue
        last = header.split(">")[-1].strip()
        if not last:
            continue
        items.append(last)
    deduped = sorted({item for item in items if item})
    return "\n".join(f"- {item}" for item in deduped[:max_items])


def _extract_candidate_topics(chunks: List[ChunkRecord], *, subject: str, max_topics: int) -> List[TopicNode]:
    """
    Fast deterministic seed list from chunk headers; LLM refines this in extraction stage.
    """
    keys: Dict[str, TopicNode] = {}
    for chunk in chunks:
        header = (chunk.header_path or "").strip()
        last = header.split(">")[-1].strip() if header else ""
        if not last:
            continue
        topic_key = _to_topic_key(subject=subject, raw_key="", display_name=last)
        if topic_key in keys:
            continue
        keys[topic_key] = TopicNode(
            subject=subject,
            topic_key=topic_key,
            display_name=last,
        )
        if len(keys) >= max_topics:
            break
    return list(keys.values())


def _candidate_extraction_prompt(
    *,
    subject: str,
    seeded_topics: List[TopicNode],
    subject_context: str,
) -> str:
    seeded = "\n".join(
        f'- {topic.topic_key} | "{topic.display_name}"' for topic in seeded_topics
    )
    return f"""
You are building a canonical prerequisite graph for {subject.upper()} interview preparation.

Input topic context from textbook chunk headers:
{subject_context or "- (none)"}

Seed topic candidates:
{seeded or "- (none)"}

Task:
1) Normalize and improve topic nodes.
2) Propose directed prerequisite edges where prerequisite must be learned before topic.
3) Keep graph compact and practical for interview prep.

Return JSON only in this exact shape:
{{
  "topics": [
    {{
      "topic_key": "{subject}:example-topic",
      "display_name": "Example Topic"
    }}
  ],
  "edges": [
    {{
      "topic_key": "{subject}:advanced-topic",
      "prerequisite_key": "{subject}:foundational-topic",
      "confidence": 0.82,
      "rationale": "Why this dependency is needed."
    }}
  ]
}}

Rules:
- topic_key must always start with "{subject}:"
- confidence must be between 0 and 1
- no self loops
- no duplicated edges
""".strip()


def _validation_prompt(
    *,
    subject: str,
    topics: List[TopicNode],
    edges: List[PrereqEdge],
) -> str:
    topics_blob = "\n".join(f"- {node.topic_key} | {node.display_name}" for node in topics)
    edges_blob = "\n".join(
        f"- {edge.prerequisite_key} -> {edge.topic_key} (confidence={edge.confidence:.2f})"
        for edge in edges
    )
    return f"""
Validate prerequisite edges for {subject.upper()}.

Allowed topics:
{topics_blob or "- (none)"}

Candidate edges:
{edges_blob or "- (none)"}

Return JSON only:
{{
  "validated_edges": [
    {{
      "topic_key": "{subject}:advanced-topic",
      "prerequisite_key": "{subject}:foundation-topic",
      "confidence": 0.74,
      "rationale": "Short reason",
      "decision": "keep|drop"
    }}
  ]
}}

Rules:
- Keep only meaningful conceptual prerequisites.
- Drop weak or non-essential dependencies.
- confidence between 0 and 1.
- Keep rationale concise.
""".strip()


def _parse_topics(raw_topics: Any, *, subject: str) -> List[TopicNode]:
    if not isinstance(raw_topics, list):
        return []
    out: list[TopicNode] = []
    seen: set[str] = set()
    for item in raw_topics:
        if not isinstance(item, dict):
            continue
        topic_key = _to_topic_key(
            subject=subject,
            raw_key=str(item.get("topic_key") or ""),
            display_name=str(item.get("display_name") or ""),
        )
        if topic_key in seen:
            continue
        seen.add(topic_key)
        display_name = str(item.get("display_name") or "").strip() or _infer_display_name(topic_key)
        out.append(
            TopicNode(
                subject=subject,
                topic_key=topic_key,
                display_name=display_name,
            )
        )
    return out


def _parse_edges(raw_edges: Any, *, subject: str) -> List[PrereqEdge]:
    if not isinstance(raw_edges, list):
        return []
    out: list[PrereqEdge] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_edges:
        if not isinstance(item, dict):
            continue
        topic_key = _to_topic_key(
            subject=subject,
            raw_key=str(item.get("topic_key") or ""),
            display_name="",
        )
        prerequisite_key = _to_topic_key(
            subject=subject,
            raw_key=str(item.get("prerequisite_key") or ""),
            display_name="",
        )
        if topic_key == prerequisite_key:
            continue
        pair = (topic_key, prerequisite_key)
        if pair in seen:
            continue
        seen.add(pair)
        try:
            confidence = float(item.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        rationale = str(item.get("rationale") or "").strip()
        out.append(
            PrereqEdge(
                subject=subject,
                topic_key=topic_key,
                prerequisite_key=prerequisite_key,
                confidence=confidence,
                rationale=rationale,
            )
        )
    return out


def _filter_edges(
    *,
    edges: Iterable[PrereqEdge],
    allowed_topic_keys: set[str],
    min_confidence: float,
) -> List[PrereqEdge]:
    out: list[PrereqEdge] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        pair = (edge.topic_key, edge.prerequisite_key)
        if pair in seen:
            continue
        seen.add(pair)
        if edge.topic_key not in allowed_topic_keys:
            continue
        if edge.prerequisite_key not in allowed_topic_keys:
            continue
        if edge.topic_key == edge.prerequisite_key:
            continue
        if edge.confidence < min_confidence:
            continue
        out.append(edge)
    return out


def _build_outgoing(edges: List[PrereqEdge]) -> Dict[str, set[str]]:
    graph: Dict[str, set[str]] = {}
    for edge in edges:
        graph.setdefault(edge.prerequisite_key, set()).add(edge.topic_key)
        graph.setdefault(edge.topic_key, set())
    return graph


def _find_cycle_nodes(graph: Dict[str, set[str]]) -> List[str]:
    visited: set[str] = set()
    in_stack: set[str] = set()
    stack: List[str] = []

    def dfs(node: str) -> List[str] | None:
        visited.add(node)
        in_stack.add(node)
        stack.append(node)
        for nxt in graph.get(node, set()):
            if nxt not in visited:
                found = dfs(nxt)
                if found:
                    return found
            elif nxt in in_stack:
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
        stack.pop()
        in_stack.remove(node)
        return None

    for node in list(graph.keys()):
        if node in visited:
            continue
        found = dfs(node)
        if found:
            return found
    return []


def _break_cycles(edges: List[PrereqEdge]) -> Tuple[List[PrereqEdge], List[dict[str, Any]]]:
    remaining = list(edges)
    removed: List[dict[str, Any]] = []

    while True:
        graph = _build_outgoing(remaining)
        cycle = _find_cycle_nodes(graph)
        if not cycle:
            break
        cycle_pairs = {(cycle[i + 1], cycle[i]) for i in range(len(cycle) - 1)}
        cycle_edges = [
            edge for edge in remaining if (edge.topic_key, edge.prerequisite_key) in cycle_pairs
        ]
        if not cycle_edges:
            break
        victim = sorted(
            cycle_edges,
            key=lambda edge: (edge.confidence, edge.topic_key, edge.prerequisite_key),
        )[0]
        remaining = [
            edge
            for edge in remaining
            if not (
                edge.topic_key == victim.topic_key
                and edge.prerequisite_key == victim.prerequisite_key
            )
        ]
        removed.append(
            {
                "topic_key": victim.topic_key,
                "prerequisite_key": victim.prerequisite_key,
                "confidence": victim.confidence,
                "reason": "cycle_break_lowest_confidence",
            }
        )

    return remaining, removed


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _subjects_from_chunks(chunks: List[ChunkRecord], requested_subject: Optional[str]) -> List[str]:
    if requested_subject:
        return [requested_subject]
    subjects = sorted({_normalize_subject(chunk.subject) for chunk in chunks if chunk.subject})
    if subjects:
        return subjects
    return ["unknown"]


def _run_subject_pipeline(
    *,
    subject: str,
    chunks: List[ChunkRecord],
    max_topics: int,
    min_confidence: float,
    model_name: Optional[str],
) -> Dict[str, Any]:
    client = create_client(model_name=model_name)

    seeded_topics = _extract_candidate_topics(chunks, subject=subject, max_topics=max_topics)
    subject_context = _build_subject_context(chunks)

    extraction_prompt = _candidate_extraction_prompt(
        subject=subject,
        seeded_topics=seeded_topics,
        subject_context=subject_context,
    )
    extraction_raw = client.generate_single(extraction_prompt, max_tokens=2400, temperature=0.1)
    extraction_json = _extract_json_object(extraction_raw) or {}
    extracted_topics = _parse_topics(extraction_json.get("topics"), subject=subject)
    if not extracted_topics:
        extracted_topics = seeded_topics
    topic_by_key = {topic.topic_key: topic for topic in extracted_topics}
    extracted_edges = _parse_edges(extraction_json.get("edges"), subject=subject)

    validation_prompt = _validation_prompt(
        subject=subject,
        topics=list(topic_by_key.values()),
        edges=extracted_edges,
    )
    validation_raw = client.generate_single(validation_prompt, max_tokens=2200, temperature=0.1)
    validation_json = _extract_json_object(validation_raw) or {}
    validated_edges_raw = _parse_edges(validation_json.get("validated_edges"), subject=subject)

    keep_decisions: Dict[tuple[str, str], bool] = {}
    if isinstance(validation_json.get("validated_edges"), list):
        for row in validation_json["validated_edges"]:
            if not isinstance(row, dict):
                continue
            topic_key = _to_topic_key(
                subject=subject,
                raw_key=str(row.get("topic_key") or ""),
                display_name="",
            )
            prerequisite_key = _to_topic_key(
                subject=subject,
                raw_key=str(row.get("prerequisite_key") or ""),
                display_name="",
            )
            decision = str(row.get("decision") or "keep").strip().lower()
            keep_decisions[(topic_key, prerequisite_key)] = decision == "keep"

    merged_edges: List[PrereqEdge] = []
    for edge in validated_edges_raw:
        decision = keep_decisions.get((edge.topic_key, edge.prerequisite_key), True)
        if not decision:
            continue
        merged_edges.append(edge)

    allowed = set(topic_by_key.keys())
    filtered = _filter_edges(
        edges=merged_edges,
        allowed_topic_keys=allowed,
        min_confidence=min_confidence,
    )
    acyclic_edges, removed_cycles = _break_cycles(filtered)

    return {
        "subject": subject,
        "topics": [dataclasses.asdict(topic) for topic in topic_by_key.values()],
        "candidate_edges": [dataclasses.asdict(edge) for edge in extracted_edges],
        "validated_edges": [dataclasses.asdict(edge) for edge in acyclic_edges],
        "cycle_drops": removed_cycles,
        "stats": {
            "seeded_topics": len(seeded_topics),
            "extracted_topics": len(extracted_topics),
            "candidate_edges": len(extracted_edges),
            "validated_edges_before_cycle_break": len(filtered),
            "validated_edges_after_cycle_break": len(acyclic_edges),
            "cycle_drops": len(removed_cycles),
            "min_confidence": min_confidence,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build canonical topic dependency graph from chunks with LLM-assisted extraction.",
    )
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=_DEFAULT_INPUT_CHUNKS,
        help="Path to chunks JSONL",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Directory for output graph artifacts",
    )
    parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help="Optional subject filter (os, dbms, cn)",
    )
    parser.add_argument(
        "--max-topics",
        type=int,
        default=120,
        help="Max topic nodes per subject for extraction context",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.70,
        help="Minimum confidence threshold for keeping edges",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Optional LLM model override",
    )
    args = parser.parse_args()

    chunks = load_chunks(path=args.chunks_path)
    subjects = _subjects_from_chunks(
        chunks,
        requested_subject=_normalize_subject(args.subject) if args.subject else None,
    )

    run_time = dt.datetime.now(dt.timezone.utc).isoformat()
    aggregate_subjects: List[dict[str, Any]] = []

    for subject in subjects:
        scoped = [chunk for chunk in chunks if _normalize_subject(chunk.subject) == subject]
        if not scoped:
            print(f"[skip] subject={subject} has no chunks")
            continue
        print(f"[run] subject={subject} chunks={len(scoped)}")
        result = _run_subject_pipeline(
            subject=subject,
            chunks=scoped,
            max_topics=max(10, args.max_topics),
            min_confidence=max(0.0, min(1.0, args.min_confidence)),
            model_name=args.model,
        )
        aggregate_subjects.append(result)

        candidate_path = args.output_dir / f"topic_graph.{subject}.candidates.json"
        validated_path = args.output_dir / f"topic_graph.{subject}.validated.json"
        _write_json(
            candidate_path,
            {
                "generated_at": run_time,
                "subject": subject,
                "topics": result["topics"],
                "candidate_edges": result["candidate_edges"],
                "stats": result["stats"],
            },
        )
        _write_json(
            validated_path,
            {
                "generated_at": run_time,
                "subject": subject,
                "topics": result["topics"],
                "validated_edges": result["validated_edges"],
                "cycle_drops": result["cycle_drops"],
                "stats": result["stats"],
            },
        )
        print(
            "[done] subject=%s topics=%s candidate_edges=%s validated_edges=%s cycle_drops=%s"
            % (
                subject,
                len(result["topics"]),
                len(result["candidate_edges"]),
                len(result["validated_edges"]),
                len(result["cycle_drops"]),
            )
        )

    aggregate_path = args.output_dir / "topic_graph.validated.json"
    _write_json(
        aggregate_path,
        {
            "generated_at": run_time,
            "subjects": [
                {
                    "subject": result["subject"],
                    "topics": result["topics"],
                    "validated_edges": result["validated_edges"],
                    "cycle_drops": result["cycle_drops"],
                    "stats": result["stats"],
                }
                for result in aggregate_subjects
            ],
        },
    )
    print(f"[write] aggregate={aggregate_path}")


if __name__ == "__main__":
    main()
