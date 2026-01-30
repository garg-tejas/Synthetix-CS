# SLM-Based RAG System

A complete RAG (Retrieval-Augmented Generation) pipeline with agentic orchestration, multi-stage retrieval, and web interface for technical Q&A on Operating Systems, Database Management Systems, and Computer Networks.

## Project Structure

```
slm-rag/
├── src/
│   ├── rag/           # Retrieval components (BM25, dense, hybrid)
│   ├── generation/    # Answer generation (Phase 2)
│   ├── orchestrator/  # Agentic layer (Phase 3)
│   ├── api/           # FastAPI backend (Phase 4)
│   └── llm/           # LLM client (Z.AI/GLM, ModelScope, OpenAI-compatible)
├── data/              # Chunks and questions datasets
├── scripts/           # CLI utilities and preprocessing
├── tests/             # Test suite
└── frontend/          # Web UI (Phase 5)
```

## Features

- **Hybrid Retrieval**: BM25 sparse + dense semantic search with RRF fusion
- **Query Understanding**: Intent detection and query rewriting
- **Reranking**: Cross-encoder reranking for improved results
- **HYDE**: Hypothetical Document Embeddings for better semantic search
- **Answer Generation**: Context builder with [1], [2] citation markers; LLM generation; citation extraction from response text

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env: set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL for Z.AI/GLM (see .env.example)
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Build or Update Chunks (Optional)

If you need to (re)create `data/chunks.jsonl` with subject tags and QA exclusions:

```bash
# 1. Put raw textbook .mmd files in books/mmd/
# 2. Clean them (writes books/mmd_clean/)
uv run python scripts/preprocess/clean_mmd.py

# 3. Build chunks (writes data/chunks.jsonl with subject, excludes references/exercises/appendix)
uv run python scripts/build_chunks.py
```

If `books/mmd_clean/` already exists, run only step 3.

### 4. Generate QA Pairs (Evaluation Dataset)

```bash
# Test with small subset
uv run python -m eval.generation.batch_generate --max-chunks 10 --questions-per-chunk 2

# Generate for specific subject
uv run python -m eval.generation.batch_generate --subject os --max-chunks 50
```

### 5. Evaluate Retrieval

```bash
# Evaluate retrieval quality
uv run python -m eval.runners.run_question_eval --top-k 5

# Test retrieval behavior
uv run python -m eval.runners.run_evaluation --subject os
```

See [docs/QA_GENERATION.md](docs/QA_GENERATION.md) and [docs/EVALUATION.md](docs/EVALUATION.md) for detailed guides.

## Environment Variables

Create a `.env` file in the project root. **Z.AI (GLM-4.7-flash)** is the default when set:

```bash
# Z.AI / GLM (recommended)
LLM_BASE_URL=https://api.z.ai/api/paas/v4/
LLM_API_KEY=your-Z.AI-api-key
LLM_MODEL=glm-4.7-flash
```

Alternatively, use ModelScope:

```bash
MODELSCOPE_API_TOKEN=your_token_here
MODELSCOPE_MODEL=deepseek-ai/DeepSeek-R1-0528  # Optional
```

## Development Status

Phases:

- **Phase 1**: Core RAG Pipeline (done)
- **Phase 2**: Answer Generation with Citations (done)
- **Phase 3**: Agentic Orchestrator (next)
- **Phase 4**: FastAPI Backend
- **Phase 5**: Frontend + Documentation

## Documentation

- **Architecture**: See `docs/ARCHITECTURE.md` (coming soon)
- **API Reference**: See `docs/API.md` (coming soon)
