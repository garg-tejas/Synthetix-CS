"""
Prompt templates for QA generation and quality review from textbook chunks.
"""

import json

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
        "definition": "deep conceptual questions (why the concept matters, trade-offs, and failure implications)",
        "algorithm": "procedural deep-dive questions (steps, edge cases, complexity, and practical constraints)",
        "protocol": "mechanism and comparison questions (how it works, why design choices exist, and protocol trade-offs)",
        "section": "conceptual and applied questions (reasoning, comparisons, and practical behavior)",
    }
    suggested_types = question_type_hints.get(
        chunk.chunk_type, "conceptual, procedural, comparative, and interview-oriented factual questions"
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
2. Are appropriate for technical placement interviews (NOT context-specific like "according to the given text" or "as used in describing X")
3. Have clear, concise answers (2-4 sentences)
4. Are standalone questions that could be asked in a real interview without referencing the textbook

IMPORTANT RULES:
- Avoid textbook-framing phrases (e.g., "according to the given text", "as used in describing", "define the term as used in").
- Avoid shallow prompts like "What is the Internet?" or single-term definition drills with no depth.
- At least half of the questions must require reasoning about mechanism, trade-offs, failure modes, or practical implications.
- Prefer prompts a placement interviewer would ask after fundamentals, not first-day basics.

Focus on generating {suggested_types} that this chunk itself can answer completely.

For each question, provide:
- query: The question text (natural language, as a student would ask in an interview)
- answer: A complete answer (2-4 sentences) that accurately explains the concept
- question_type: One of [definition, procedural, comparative, factual]
- atomic_facts: List of 2-4 key facts that the answer should cover
- difficulty: One of [easy, medium, hard] based on interview difficulty
- placement_interview_score: An integer from 0-100 rating how likely this question is to be asked in a real technical placement interview. Score 0-30 for questions that are too context-specific, theoretical without practical value, or too obscure. Score 70-100 for questions that are commonly asked, test practical knowledge, and are relevant to real-world scenarios.

Return ONLY valid JSON, no markdown formatting, no code blocks:
{{
  "questions": [
    {{
      "query": "...",
      "answer": "...",
      "question_type": "...",
      "atomic_facts": ["...", "..."],
      "difficulty": "...",
      "placement_interview_score": 85
    }}
  ]
}}
"""

    return prompt


def build_qa_review_prompt(
    *,
    chunk: ChunkRecord,
    candidate_questions: list[dict],
    min_score: int = 70,
    allow_rewrite: bool = True,
) -> str:
    """
    Build prompt for second-pass LLM review of generated questions.
    """
    chunk_text = chunk.text[:1200].replace("\n", " ")
    if len(chunk.text) > 1200:
        chunk_text += "..."

    candidates_json = json.dumps(candidate_questions, ensure_ascii=False, indent=2)
    rewrite_instruction = (
        "For `decision: rewrite`, include a fully rewritten question object in `revised`."
        if allow_rewrite
        else "Do not rewrite. Use only keep/reject decisions."
    )

    return f"""You are a senior technical interviewer reviewing generated interview questions.

Goal:
- Keep only questions that match real technical placement interview depth.
- Reject shallow foundation prompts (e.g., "What is the Internet?") and textbook-style phrasing.
- Prefer mechanism, trade-off, failure-mode, comparison, and practical reasoning questions.
- Important: do NOT reject a question only because it starts with "What is".
  Some definition prompts are valid interview questions (e.g., deadlock, ACID, soft delete vs hard delete context).
  Judge by interview relevance and depth of expected answer, not prefix patterns.
- Be harsh and conservative: if uncertain, reject.
- Assume interview time is limited; keep only questions likely to be asked in real OS/DBMS/CN screening rounds.

Source chunk:
- Header: {chunk.header_path}
- Type: {chunk.chunk_type}
- Key terms: {", ".join(chunk.key_terms[:12]) if chunk.key_terms else "N/A"}
- Text snippet: {chunk_text}

Candidate questions JSON:
{candidates_json}

Rubric (0-100):
- 90-100: Strong interview question with depth and practical reasoning.
- 75-89: Good interview question, minor wording issues.
- 60-74: Borderline, can be salvaged with rewrite.
- 0-59: Too shallow/trivial/off-topic for interviews.

Rules:
1. Evaluate each candidate by `index`.
2. `decision` must be one of: keep, rewrite, reject.
3. A question can be kept only if score >= {min_score}.
4. {rewrite_instruction}
5. If rewritten, keep the concept answerable from the source chunk.
6. Rewritten object schema must include:
   - query
   - answer
   - question_type in [definition, procedural, comparative, factual]
   - atomic_facts (2-4 items)
   - difficulty in [easy, medium, hard]

Return ONLY JSON:
{{
  "results": [
    {{
      "index": 0,
      "decision": "keep|rewrite|reject",
      "score": 0,
      "reasons": ["..."],
      "revised": {{
        "query": "...",
        "answer": "...",
        "question_type": "procedural",
        "atomic_facts": ["...", "..."],
        "difficulty": "medium"
      }}
    }}
  ]
}}
"""


def build_bulk_qa_scoring_prompt(
    *,
    candidate_questions: list[dict],
    min_score: int = 70,
    allow_rewrite: bool = False,
) -> str:
    """
    Build a prompt for bulk interview scoring of existing question sets.
    """
    candidates_json = json.dumps(candidate_questions, ensure_ascii=False, indent=2)
    rewrite_rule = (
        "If decision is rewrite, return a full `revised` object with the same schema."
        if allow_rewrite
        else "Do not rewrite. Use only keep or reject."
    )

    return f"""You are evaluating technical interview questions for placement preparation quality.

Task:
- Score each candidate question for whether it would realistically be asked in a technical interview.
- Use score 0-100 and assign decision keep/rewrite/reject.
- Be concept-aware, not keyword-biased:
  - "What is deadlock?" can be valid when expected answer includes conditions and implications.
  - "What is the Internet?" is usually too generic for interview depth unless contextualized.
- Prefer questions about mechanisms, trade-offs, debugging, failure modes, design decisions, and practical behavior.
- Reject textbook-only phrasing or trivia.
- Be strict: keep only high-confidence interview questions; if unsure, reject.
- Treat acceptance budget as scarce: only retain questions likely to appear in real interview rounds.

Quality rubric:
- 90-100: strong interview question, highly relevant and deep.
- 75-89: good interview question, minor issues.
- 60-74: borderline; may be rewritten.
- 0-59: weak, generic, trivial, or off-target.

Strong keep signals:
- canonical interview concept plus practical implications (deadlock, starvation, ACID anomalies, indexing trade-offs, isolation behavior, congestion control behavior).
- mechanism/trade-off/comparison/debug framing that tests understanding beyond rote definitions.

Strong reject signals:
- chapter-introduction recall or broad textbook framing.
- generic high-school level fundamentals without technical depth.
- questions unlikely to be asked in a hiring interview even if factually correct.

Constraints:
1. Process by `index`.
2. Keep only if score >= {min_score}.
3. {rewrite_rule}
4. Reasons should be brief and concrete.
5. Return only valid JSON.

Input candidates:
{candidates_json}

Output format:
{{
  "results": [
    {{
      "index": 0,
      "decision": "keep|rewrite|reject",
      "score": 0,
      "reasons": ["..."],
      "revised": {{
        "query": "...",
        "answer": "...",
        "question_type": "definition|procedural|comparative|factual",
        "difficulty": "easy|medium|hard",
        "atomic_facts": ["...", "..."]
      }}
    }}
  ]
}}
"""
