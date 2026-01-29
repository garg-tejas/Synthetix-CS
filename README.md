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

### 3. Run Retrieval Demo

```bash
# Using the hybrid searcher
uv run python -c "from src.rag import HybridSearcher, load_chunks; chunks = load_chunks(); searcher = HybridSearcher.from_chunks(chunks); results = searcher.search('what is a deadlock', top_k=5); print(results[0][0].text[:200])"
```

## Environment Variables

Create a `.env` file in the project root:

```bash
MODELSCOPE_API_TOKEN=your_token_here
MODELSCOPE_MODEL=zai-org/GLM-4.7-Flash  # Optional
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
