"""
Simple CLI to run the canned test queries against the current retrieval stack.

Usage (from repo root):

    uv run python -m eval.evaluate.run_test_queries
    uv run python -m eval.evaluate.run_test_queries --query "what is tcp 3 way handshake"
    uv run python -m eval.evaluate.run_test_queries --subject os
"""

from __future__ import annotations

import argparse
from typing import List

from eval.rag.index import load_chunks
from eval.rag.search_cli import HybridSearcher
from .test_queries import TestQuery, get_test_queries, get_queries_by_subject


def _format_result_header(idx: int, query: str, description: str) -> str:
    return f"\n[{idx}] {query}\n    {description}\n"


def _print_single_query_results(
    searcher: HybridSearcher,
    tq: TestQuery,
    top_k: int,
    idx: int | None = None,
) -> None:
    """Run one TestQuery and pretty‑print the top‑k hits."""
    header = _format_result_header(idx or 1, tq.query, tq.description)
    print(header, end="")

    results = searcher.search(tq.query, top_k=top_k)

    if not results:
        print("    (no results)")
        return

    noise_hits = 0
    required_hits = 0

    for rank, (chunk, score) in enumerate(results, start=1):
        # Quick labels for eyeballing relevance
        is_type_ok = chunk.chunk_type in tq.relevant_chunk_types
        header_text = (chunk.header_path + " " + chunk.text[:200]).lower()
        has_negative = any(pat.lower() in header_text for pat in tq.negative_patterns)
        if has_negative:
            noise_hits += 1

        # Count how many hits have the "required" types, if any.
        if getattr(tq, "required_chunk_types", None):
            if chunk.chunk_type in (tq.required_chunk_types or []):
                required_hits += 1

        type_flag = "✓" if is_type_ok else " "
        noise_flag = "✗NOISE" if has_negative else "     "

        print(
            f"    {rank:2d}. {score:6.4f}  [{chunk.chunk_type:<12}] "
            f"{type_flag} {noise_flag}  {chunk.id}"
        )
        print(f"        Header: {chunk.header_path}")
        # Truncate text for readability
        snippet = chunk.text.replace("\n", " ")[:160]
        print(f"        Text  : {snippet}...")

    # If this TestQuery encodes an expectation about noise, report it.
    if getattr(tq, "max_noise_at_k", None) is not None:
        expected = tq.max_noise_at_k
        status = "PASS" if noise_hits <= expected else "FAIL"
        print(f"    Noise@{top_k}: {noise_hits} (expected ≤ {expected}) -> {status}")

    # If this TestQuery encodes an expectation about required chunk types,
    # report whether we saw enough of them.
    if getattr(tq, "min_required_hits_at_k", None) is not None and getattr(
        tq, "required_chunk_types", None
    ):
        expected_req = tq.min_required_hits_at_k or 0
        status_req = "PASS" if required_hits >= expected_req else "FAIL"
        print(
            "    RequiredTypes@{k}: {hits} (expected ≥ {exp}) -> {status}".format(
                k=top_k, hits=required_hits, exp=expected_req, status=status_req
            )
        )


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run canned retrieval test queries against the current hybrid searcher."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to show per query (default: 5)",
    )
    parser.add_argument(
        "--subject",
        choices=["os", "dbms", "cn"],
        help="Filter test queries by subject (os/dbms/cn).",
    )
    parser.add_argument(
        "--query",
        help="Run a single ad‑hoc query string instead of the canned set.",
    )

    args = parser.parse_args(argv)

    chunks = load_chunks()
    # Use full hybrid + reranker stack for evaluation.
    searcher = HybridSearcher.from_chunks(chunks, use_reranker=True)

    # Ad‑hoc single query mode
    if args.query:
        tq = TestQuery(
            query=args.query,
            description="Ad‑hoc query",
            relevant_chunk_types=["definition", "section", "algorithm", "protocol"],
            negative_patterns=[],
            expected_concepts=[],
        )
        _print_single_query_results(searcher, tq, top_k=args.top_k, idx=1)
        return

    # Canned test set mode
    if args.subject:
        test_queries = get_queries_by_subject(args.subject)
    else:
        test_queries = get_test_queries()

    if not test_queries:
        print("No test queries found.")
        return

    print(f"Running {len(test_queries)} test queries (top_k={args.top_k})...")

    for i, tq in enumerate(test_queries, start=1):
        _print_single_query_results(searcher, tq, top_k=args.top_k, idx=i)


if __name__ == "__main__":
    main()

