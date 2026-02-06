"""
Analyze LLM scoring payload size for question batches.

This helper estimates character usage for the same fields sent by
`eval.generation.score_questions` -> `score_questions_batch_with_llm`.
Use it to tune `--batch-size` and `--max-batch-chars`.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List


FIELDS = [
    "query",
    "question_type",
    "difficulty",
    "source_subject",
    "source_header",
]


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def _string_len(value: Any) -> int:
    if value is None:
        return 0
    return len(str(value))


def _percentile(values: List[int], pct: float) -> int:
    if not values:
        return 0
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    sorted_vals = sorted(values)
    rank = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_vals[lo]
    low_val = sorted_vals[lo]
    high_val = sorted_vals[hi]
    weight = rank - lo
    return int(round(low_val + (high_val - low_val) * weight))


def _build_payload_row(question: Dict[str, Any], index: int) -> Dict[str, Any]:
    # Keep this aligned with eval/generation/llm_review.py:score_questions_batch_with_llm
    return {
        "index": index,
        "query": question.get("query"),
        "question_type": question.get("question_type"),
        "difficulty": question.get("difficulty"),
        "source_subject": question.get("source_subject"),
        "source_header": question.get("source_header"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze payload character lengths for LLM scoring batches.",
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Input JSONL file (generated/scored question rows)",
    )
    parser.add_argument(
        "--subject",
        choices=["os", "dbms", "cn"],
        help="Optional subject filter",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Optional cap on number of rows to analyze",
    )
    parser.add_argument(
        "--target-max-chars",
        type=int,
        default=24000,
        help="Target `--max-batch-chars` for recommendation math",
    )
    parser.add_argument(
        "--target-batch-size",
        type=int,
        default=20,
        help="Target `--batch-size` for recommendation math",
    )
    parser.add_argument(
        "--safety-margin",
        type=float,
        default=0.9,
        help=(
            "Safety multiplier for recommendations (default: 0.9 means keep "
            "10%% headroom)"
        ),
    )
    args = parser.parse_args()

    if not args.input_file.exists():
        raise SystemExit(f"Input file not found: {args.input_file}")

    rows: List[Dict[str, Any]] = []
    for row in _iter_jsonl(args.input_file):
        if args.subject and row.get("source_subject") != args.subject:
            continue
        rows.append(row)
        if args.sample_size is not None and len(rows) >= args.sample_size:
            break

    total = len(rows)
    if total == 0:
        raise SystemExit("No rows available after filters.")

    per_field_lengths: Dict[str, List[int]] = {f: [] for f in FIELDS}
    row_payload_chars: List[int] = []
    row_compact_chars: List[int] = []

    for i, row in enumerate(rows):
        for field in FIELDS:
            val = row.get(field)
            per_field_lengths[field].append(_string_len(val))

        payload_row = _build_payload_row(row, i)
        compact = json.dumps(payload_row, ensure_ascii=False, separators=(",", ":"))
        pretty = json.dumps(payload_row, ensure_ascii=False, indent=2)
        row_compact_chars.append(len(compact))
        row_payload_chars.append(len(pretty))

    p50 = _percentile(row_payload_chars, 50)
    p90 = _percentile(row_payload_chars, 90)
    p95 = _percentile(row_payload_chars, 95)
    p99 = _percentile(row_payload_chars, 99)
    avg_payload = int(round(statistics.fmean(row_payload_chars)))
    avg_compact = int(round(statistics.fmean(row_compact_chars)))

    print("Scoring Payload Length Analysis")
    print("=" * 40)
    print(f"Input: {args.input_file}")
    if args.subject:
        print(f"Subject: {args.subject}")
    if args.sample_size:
        print(f"Sample size cap: {args.sample_size}")
    print(f"Rows analyzed: {total}")

    print("\nPer-field character lengths (avg / p90 / p95 / max)")
    for field in FIELDS:
        vals = per_field_lengths[field]
        avg = int(round(statistics.fmean(vals)))
        print(
            f"- {field:24s} "
            f"{avg:5d} / {_percentile(vals, 90):5d} / {_percentile(vals, 95):5d} / {max(vals):5d}"
        )

    print(
        "\nSerialized payload-row chars (JSON entry actually sent to scoring prompt):"
    )
    print(
        f"- pretty avg={avg_payload}, p50={p50}, p90={p90}, p95={p95}, p99={p99}, max={max(row_payload_chars)}"
    )
    print(
        f"- compact avg={avg_compact}, p95={_percentile(row_compact_chars, 95)}, max={max(row_compact_chars)}"
    )

    # Batch recommendations.
    safety = max(0.1, min(1.0, args.safety_margin))
    safe_target_chars = int(args.target_max_chars * safety)
    safe_batch_from_p95 = max(1, safe_target_chars // max(1, p95))
    safe_batch_from_p99 = max(1, safe_target_chars // max(1, p99))

    recommended_chars_for_target_batch_p95 = int(
        math.ceil(args.target_batch_size * p95 / max(0.1, safety))
    )
    recommended_chars_for_target_batch_p99 = int(
        math.ceil(args.target_batch_size * p99 / max(0.1, safety))
    )

    print("\nRecommendation Helpers")
    print(
        f"- For target max chars={args.target_max_chars} and safety={safety:.2f}: "
        f"batch_size <= {safe_batch_from_p95} (p95) or <= {safe_batch_from_p99} (p99)"
    )
    print(
        f"- For target batch_size={args.target_batch_size}: "
        f"max_batch_chars ~= {recommended_chars_for_target_batch_p95} (p95) "
        f"or {recommended_chars_for_target_batch_p99} (p99)"
    )


if __name__ == "__main__":
    main()
