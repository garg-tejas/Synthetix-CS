"""Configuration for answer generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GenerationConfig:
    """Settings for RAG answer generation."""

    max_tokens: int = 1024
    temperature: float = 0.3
    context_max_tokens: int = 2000
