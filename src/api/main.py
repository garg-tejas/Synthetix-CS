"""
FastAPI application for the RAG API.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import build_agent_and_chunks
from .routes import router
from .quiz_routes import router as quiz_router
from src.auth.routes import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load chunks and build agent on startup; clear on shutdown."""
    agent, retriever, chunks_by_id, chunks_loaded = build_agent_and_chunks()
    app.state.agent = agent
    app.state.retriever = retriever
    app.state.chunks_by_id = chunks_by_id or {}
    app.state.chunks_loaded = chunks_loaded
    app.state.sessions = {}
    yield
    app.state.sessions.clear()


app = FastAPI(
    title="Synthetix-CS API",
    description="RAG API for technical Q&A (OS, DBMS, Computer Networks)",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(auth_router)
app.include_router(quiz_router)
