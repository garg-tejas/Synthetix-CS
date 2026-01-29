"""
Prompt templates for QA generation from textbook chunks.
"""

from typing import List, Optional

from src.rag.index import ChunkRecord


def _summarize_neighbor(chunk: ChunkRecord) -> str:
    """
    Build a short, human-readable summary for a neighboring chunk.
    """
    prefix = f"{chunk.header_path} ({chunk.chunk_type})"
    snippet = chunk.text[:300].replace("\n", " ")
    if len(chunk.text) > 300:
        snippet += "..."
    return f"{prefix}: {snippet}"


def build_qa_generation_prompt(
    chunk: ChunkRecord,
    num_questions: int = 2,
    prev_chunk: Optional[ChunkRecord] = None,
    next_chunk: Optional[ChunkRecord] = None,
) -> str:
    """
    Build a prompt for generating questions from a chunk.
    
    Args:
        chunk: The chunk to generate questions from
        num_questions: Number of questions to generate (1-3)
        prev_chunk: Optional previous chunk in logical order
        next_chunk: Optional next chunk in logical order
    
    Returns:
        Formatted prompt string
    """
    # Truncate text to avoid context limits
    text_snippet = chunk.text[:1500].replace("\n", " ")
    if len(chunk.text) > 1500:
        text_snippet += "..."

    key_terms_str = ", ".join(chunk.key_terms[:10]) if chunk.key_terms else "N/A"

    # Optional heuristic question hints derived during preprocessing.
    potential_qs = getattr(chunk, "potential_questions", None) or []
    potential_qs_str = ""
    if potential_qs:
        joined = "\n".join(f"- {q}" for q in potential_qs[:3])
        potential_qs_str = (
            "\nHere are example questions this chunk is well-suited to answer:\n"
            f"{joined}\n"
        )

    # Optional local context from neighboring chunks
    context_lines: List[str] = []
    if prev_chunk is not None:
        context_lines.append(
            "- Previous chunk: " + _summarize_neighbor(prev_chunk)
        )
    if next_chunk is not None:
        context_lines.append(
            "- Next chunk: " + _summarize_neighbor(next_chunk)
        )
    context_block = ""
    if context_lines:
        context_block = (
            "\nThis chunk appears in the following local context:\n"
            + "\n".join(context_lines)
            + "\n"
        )

    # Suggest question types based on chunk_type
    question_type_hints = {
        "definition": "definition questions (what is X, define X)",
        "algorithm": "procedural questions (how to do X, explain the steps)",
        "protocol": "comparative or definition questions (compare X and Y, what is X)",
        "section": "factual or comprehension questions (explain X, describe X)",
    }
    suggested_types = question_type_hints.get(
        chunk.chunk_type, "definition, procedural, or factual questions"
    )

    prompt = f"""You are generating questions for a placement preparation system covering Operating Systems, Database Management Systems, and Computer Networks.

Given this textbook chunk:

**Header:** {chunk.header_path}
**Type:** {chunk.chunk_type}
**Key Terms:** {key_terms_str}
{context_block}{potential_qs_str}**Text:**
{text_snippet}

Generate {num_questions} high-quality questions that:
1. Test understanding of the core concepts in this chunk
2. Are appropriate for technical placement interviews
3. Have clear, concise answers (2-4 sentences)
4. Are grounded primarily in this focal chunk, using the neighbor context only for clarification

Focus on generating {suggested_types} that this chunk itself can answer completely.

For each question, provide:
- query: The question text (natural language, as a student would ask)
- answer: A complete answer (2-4 sentences) that accurately explains the concept
- question_type: One of [definition, procedural, comparative, factual]
- atomic_facts: List of 2-4 key facts that the answer should cover
- difficulty: One of [easy, medium, hard] based on interview difficulty

Return ONLY valid JSON, no markdown formatting, no code blocks:
{{
  "questions": [
    {{
      "query": "...",
      "answer": "...",
      "question_type": "...",
      "atomic_facts": ["...", "..."],
      "difficulty": "..."
    }}
  ]
}}
"""

    return prompt


def build_batch_prompt(chunks: List[ChunkRecord], questions_per_chunk: int = 1) -> str:
    """
    Build a prompt for generating questions from multiple chunks (for batch processing).
    
    This is less ideal than per-chunk prompts but can be faster.
    """
    if not chunks:
        return ""

    prompts = []
    for i, chunk in enumerate(chunks, 1):
        prompts.append(f"\n--- Chunk {i} ---")
        prompts.append(f"Header: {chunk.header_path}")
        prompts.append(f"Type: {chunk.chunk_type}")
        prompts.append(f"Text: {chunk.text[:800]}...")

    combined_text = "\n".join(prompts)

    prompt = f"""Generate {questions_per_chunk} question(s) for each of the following textbook chunks.

{combined_text}

For each chunk, generate questions following the same format as the single-chunk prompt.
Return JSON with questions grouped by chunk index.
"""

    return prompt
