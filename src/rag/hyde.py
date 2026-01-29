"""
HYDE (Hypothetical Document Embeddings) helper.

Generates a hypothetical answer paragraph and uses it as the query for semantic retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..llm.client import ModelScopeClient, create_client


@dataclass
class HydeGenerator:
    """Thin wrapper over ModelScopeClient for HYDE-style retrieval."""

    client: ModelScopeClient

    @classmethod
    def from_env(
        cls,
        model_name: Optional[str] = None,
        modelscope_token: Optional[str] = None,
    ) -> "HydeGenerator":
        """Construct a HYDE generator using environment-based configuration."""
        client = create_client(model_name=model_name, modelscope_token=modelscope_token)
        return cls(client=client)

    def generate_hypothetical_answer(self, query: str) -> str:
        """Generate a short hypothetical answer paragraph for the given query."""
        prompt = (
            f'Given the technical question: "{query}"\n'
            "Write a short, textbook-style paragraph that directly and precisely answers "
            "this question. Focus on the key concepts, definitions, and steps. "
            "Limit the answer to 2-3 sentences."
        )
        return self.client.generate_single(
            prompt,
            max_tokens=256,
            temperature=0.3,
            top_p=0.9,
            stop=None,
        ).strip()
