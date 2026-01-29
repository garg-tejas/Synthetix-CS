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
│   └── llm/           # ModelScope API client
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
- **Context Expansion**: Neighboring chunk expansion for better context

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your ModelScope API token
# Get token from: https://modelscope.cn/my/myaccesstoken
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Generate QA Pairs (Evaluation Dataset)

```bash
# Test with small subset
uv run python -m eval.generation.batch_generate --max-chunks 10 --questions-per-chunk 2

# Generate for specific subject
uv run python -m eval.generation.batch_generate --subject os --max-chunks 50
```

### 4. Evaluate Retrieval

```bash
# Evaluate retrieval quality
uv run python -m eval.runners.run_question_eval --top-k 5

# Test retrieval behavior
uv run python -m eval.runners.run_evaluation --subject os
```

See [docs/QA_GENERATION.md](docs/QA_GENERATION.md) and [docs/EVALUATION.md](docs/EVALUATION.md) for detailed guides.

## Environment Variables

Create a `.env` file in the project root:

```bash
MODELSCOPE_API_TOKEN=your_token_here
MODELSCOPE_MODEL=deepseek-ai/DeepSeek-R1-0528  # Optional
```

## Development Status

This project is structured in 5 phases:

- **Phase 1**: Core RAG Pipeline (Current)
- **Phase 2**: Answer Generation with Citations (Next)
- **Phase 3**: Agentic Orchestrator
- **Phase 4**: FastAPI Backend
- **Phase 5**: Frontend + Documentation

## Documentation

- **Architecture**: See `docs/ARCHITECTURE.md` (coming soon)
- **API Reference**: See `docs/API.md` (coming soon)
