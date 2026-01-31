"""
In-memory conversation memory for follow-up context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Turn:
    """Single conversation turn."""

    query: str
    answer: str
    citation_chunk_ids: List[str] = field(default_factory=list)


class ConversationMemory:
    """In-memory list of turns; last N used as context for follow-ups."""

    def __init__(self, max_turns: int = 10):
        self._turns: List[Turn] = []
        self.max_turns = max_turns

    def add_turn(
        self,
        query: str,
        answer: str,
        citation_chunk_ids: Optional[List[str]] = None,
    ) -> None:
        citation_chunk_ids = citation_chunk_ids or []
        self._turns.append(Turn(query=query, answer=answer, citation_chunk_ids=citation_chunk_ids))
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns :]

    def get_relevant_context(self, query: str, last_n: int = 3) -> str:
        """Return last N turns as a string for context (e.g. for query analyzer or prompt)."""
        if not self._turns:
            return ""
        turns = self._turns[-last_n:]
        parts = []
        for t in turns:
            parts.append(f"Q: {t.query}\nA: {t.answer}")
        return "\n\n".join(parts)

    def get_history(self, last_n: int = 5) -> List[dict]:
        """Return last N turns as list of dicts for the query analyzer."""
        if not self._turns:
            return []
        turns = self._turns[-last_n:]
        return [{"query": t.query, "answer": t.answer} for t in turns]

    def clear(self) -> None:
        self._turns.clear()
