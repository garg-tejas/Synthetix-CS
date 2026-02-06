from __future__ import annotations

from eval.generation.generate_qa import generate_questions_from_chunk
from eval.generation.llm_review import review_questions_with_llm
from src.rag.index import ChunkRecord


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def generate_single(self, *_args, **_kwargs) -> str:
        if not self._responses:
            return ""
        return self._responses.pop(0)


def _chunk() -> ChunkRecord:
    return ChunkRecord(
        id="chunk_1",
        book_id="Computer Networks",
        header_path="Chapter 1 > Packet Switching",
        chunk_type="protocol",
        key_terms=["packet switching", "latency", "throughput"],
        text=(
            "Packet switching shares links among flows and improves utilization. "
            "It introduces queueing delays under congestion but avoids dedicated "
            "idle circuits for bursty traffic."
        ),
        subject="cn",
    )


def test_llm_review_rewrite_accepts_revised_question() -> None:
    client = FakeLLMClient(
        [
            """{
              "results": [
                {
                  "index": 0,
                  "decision": "rewrite",
                  "score": 84,
                  "reasons": ["original was too shallow"],
                  "revised": {
                    "query": "Why does packet switching usually provide better link utilization than circuit switching for bursty traffic?",
                    "answer": "Packet switching multiplexes many bursty flows on shared links, so capacity is not reserved for idle senders. Circuit switching reserves bandwidth even during silence, which can waste capacity. Under bursty workloads, statistical sharing tends to increase utilization while trading off queueing delay.",
                    "question_type": "comparative",
                    "atomic_facts": [
                      "circuit switching reserves idle bandwidth",
                      "packet switching statistically multiplexes flows",
                      "higher utilization comes with delay trade-offs"
                    ],
                    "difficulty": "medium"
                  }
                }
              ]
            }"""
        ]
    )
    question = {
        "query": "What is packet switching?",
        "answer": "It is a method of sending data in packets.",
        "question_type": "definition",
        "difficulty": "easy",
        "atomic_facts": ["data is split into packets", "packets are forwarded hop-by-hop"],
    }

    outcome = review_questions_with_llm(
        questions=[question],
        chunk=_chunk(),
        llm_client=client,  # type: ignore[arg-type]
        min_score=70,
        allow_rewrite=True,
    )

    assert outcome.success is True
    assert len(outcome.accepted) == 1
    rewritten = outcome.accepted[0]
    assert rewritten.get("llm_rewritten") is True
    assert rewritten["question_type"] == "comparative"
    assert rewritten["llm_review_decision"] == "rewrite"


def test_llm_review_rejects_low_score_even_if_keep() -> None:
    client = FakeLLMClient(
        [
            """{
              "results": [
                {
                  "index": 0,
                  "decision": "keep",
                  "score": 62,
                  "reasons": ["too basic for interview depth"]
                }
              ]
            }"""
        ]
    )
    question = {
        "query": "What is the Internet?",
        "answer": "The Internet is a network of networks.",
        "question_type": "definition",
        "difficulty": "easy",
        "atomic_facts": ["global network", "interconnected systems"],
    }

    outcome = review_questions_with_llm(
        questions=[question],
        chunk=_chunk(),
        llm_client=client,  # type: ignore[arg-type]
        min_score=70,
    )

    assert outcome.success is True
    assert len(outcome.accepted) == 0
    assert len(outcome.rejected) == 1


def test_generate_questions_from_chunk_llm_only_uses_second_pass() -> None:
    generation_json = """{
      "questions": [
        {
          "query": "What is packet switching?",
          "answer": "Packet switching sends data as packets.",
          "question_type": "definition",
          "atomic_facts": ["data split in packets", "packets forwarded independently"],
          "difficulty": "easy",
          "placement_interview_score": 96
        }
      ]
    }"""
    review_json = """{
      "results": [
        {
          "index": 0,
          "decision": "rewrite",
          "score": 86,
          "reasons": ["requires deeper framing"],
          "revised": {
            "query": "How does packet switching trade throughput efficiency against queueing delay during congestion?",
            "answer": "Packet switching keeps links busy by multiplexing many flows rather than reserving dedicated circuits. During congestion, queues build and delay can increase even as utilization stays high. This is a core efficiency versus latency trade-off in packet networks.",
            "question_type": "procedural",
            "atomic_facts": [
              "statistical multiplexing increases utilization",
              "congestion increases queueing delay",
              "design involves efficiency-latency trade-off"
            ],
            "difficulty": "medium"
          }
        }
      ]
    }"""

    client = FakeLLMClient([generation_json, review_json])
    result = generate_questions_from_chunk(
        _chunk(),
        client,  # type: ignore[arg-type]
        num_questions=1,
        min_score=70,
        quality_mode="llm_only",
    )

    assert len(result) == 1
    assert result[0]["llm_review_decision"] == "rewrite"
    assert result[0]["quality_score"] >= 70
    assert result[0]["query"].lower().startswith("how does packet switching")

