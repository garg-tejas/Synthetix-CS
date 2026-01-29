"""
Test queries for evaluating retrieval pipeline improvements.
Focuses on queries that previously returned noisy/irrelevant results.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TestQuery:
    """A test query with expected relevant chunk types and negative examples."""

    query: str
    description: str
    relevant_chunk_types: List[str]  # chunk types that should be relevant
    negative_patterns: List[str]     # patterns that indicate irrelevant chunks
    expected_concepts: List[str]     # key concepts that should be found
    # Optional expectation: maximum number of noisy hits allowed in top‑k
    # (as detected via negative_patterns).
    max_noise_at_k: int | None = None
    # Optional expectation: at least this many chunks in the top‑k should have
    # one of these types (good for non‑definition queries like "explain", "compare").
    required_chunk_types: List[str] | None = None
    min_required_hits_at_k: int | None = None
    
    
# Test queries based on the noisy results you identified
TEST_QUERIES = [
    TestQuery(
        query="tell me about page replacement algos",
        description="Page replacement algorithms - should exclude references/bibliography",
        relevant_chunk_types=["algorithm", "section", "definition"],
        # We previously tried to mark generic uses of the word "references"
        # as noise, but that incorrectly penalized genuinely relevant chunks
        # (e.g., "counting-based page replacement" discussing reference counts).
        # For this query we instead rely on the retrieval layer's header-based
        # filtering of true References/Bibliography sections.
        negative_patterns=[],
        expected_concepts=["page replacement", "optimal", "fifo", "lru"],
        # At least one algorithmic chunk should appear.
        required_chunk_types=["algorithm"],
        min_required_hits_at_k=1,
    ),
    
    TestQuery(
        query="what is tcp 3 way handshake",
        description="TCP handshake - should exclude TLS/auth protocol chunks",
        relevant_chunk_types=["protocol", "definition", "section"],
        negative_patterns=["tls", "authentication protocol", "record protocol"],
        expected_concepts=["tcp", "three-way handshake", "syn", "ack"],
        max_noise_at_k=0,
        required_chunk_types=["protocol"],
        min_required_hits_at_k=1,
    ),
    
    TestQuery(
        query="how to do b+ tree insertion and deletion",
        description="B+ tree operations - should focus on insertion/deletion algorithms",
        relevant_chunk_types=["algorithm", "section", "definition"],
        negative_patterns=["r tree", "spatial", "semistructured"],
        expected_concepts=["b+ tree", "insertion", "deletion", "node split"],
        max_noise_at_k=0,
        required_chunk_types=["algorithm", "section"],
        min_required_hits_at_k=1,
    ),
    
    TestQuery(
        query="what is deadlock",
        description="Deadlock definition - should boost definition chunks",
        relevant_chunk_types=["definition", "section"],
        negative_patterns=["non-deadlock", "no deadlock", "without deadlock"],
        expected_concepts=["deadlock", "starvation", "resource allocation"],
        required_chunk_types=["definition", "section"],
        min_required_hits_at_k=1,
    ),
    
    TestQuery(
        query="compare tcp and udp",
        description="Protocol comparison - should include both protocols",
        relevant_chunk_types=["protocol", "section", "comparison"],
        negative_patterns=["application layer", "presentation layer"],
        expected_concepts=["tcp", "udp", "reliable", "unreliable", "connection"],
        # Non‑definition comparison query: we want protocol‑level chunks.
        required_chunk_types=["protocol"],
        min_required_hits_at_k=1,
    ),
    
    TestQuery(
        query="explain process scheduling algorithms",
        description="Scheduling algorithms - should focus on scheduling types",
        relevant_chunk_types=["algorithm", "section", "definition"],
        negative_patterns=["job scheduling", "disk scheduling"],
        expected_concepts=["round robin", "fifo", "priority", "scheduling"],
        required_chunk_types=["algorithm", "section"],
        min_required_hits_at_k=1,
    ),
    
    TestQuery(
        query="what are acid properties in databases",
        description="ACID properties - should focus on transaction properties",
        relevant_chunk_types=["definition", "section"],
        negative_patterns=["acid rain", "chemical"],
        expected_concepts=["atomicity", "consistency", "isolation", "durability"],
        required_chunk_types=["definition", "section"],
        min_required_hits_at_k=1,
    ),
    
    TestQuery(
        query="how does virtual memory work",
        description="Virtual memory - should explain mechanisms and concepts",
        relevant_chunk_types=["section", "definition", "algorithm"],
        negative_patterns=["virtual machine", "virtual reality"],
        expected_concepts=["virtual memory", "paging", "page table", "translation"],
        max_noise_at_k=0,
    )
]


def get_test_queries() -> List[TestQuery]:
    """Return the test query set."""
    return TEST_QUERIES


def get_queries_by_subject(subject: str) -> List[TestQuery]:
    """Get queries for a specific subject (os, dbms, cn)."""
    subject_map = {
        "os": ["page replacement", "deadlock", "process scheduling", "virtual memory"],
        "dbms": ["b+ tree", "acid properties", "transaction", "indexing"],
        "cn": ["tcp", "udp", "handshake", "routing", "protocol"]
    }
    
    if subject.lower() not in subject_map:
        return TEST_QUERIES
    
    keywords = subject_map[subject.lower()]
    return [
        q for q in TEST_QUERIES 
        if any(keyword in q.query.lower() for keyword in keywords)
    ]