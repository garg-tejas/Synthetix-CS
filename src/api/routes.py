"""
API routes: chat, search, health, stats, conversation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.orchestrator import ConversationMemory

from .models import (
    ChatRequest,
    ChatResponse,
    CitationOut,
    ChunkSummary,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    SearchHit,
    StatsResponse,
)

router = APIRouter(prefix="/api", tags=["api"])


def _get_state(request: Request) -> tuple[Any, Any, dict, int]:
    agent = getattr(request.app.state, "agent", None)
    retriever = getattr(request.app.state, "retriever", None)
    chunks_by_id = getattr(request.app.state, "chunks_by_id", {})
    chunks_loaded = getattr(request.app.state, "chunks_loaded", 0)
    return agent, retriever, chunks_by_id, chunks_loaded


def _get_sessions(request: Request) -> dict[str, ConversationMemory]:
    sessions = getattr(request.app.state, "sessions", None)
    if sessions is None:
        request.app.state.sessions = {}
        sessions = request.app.state.sessions
    return sessions


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Health check."""
    _, _, _, chunks_loaded = _get_state(request)
    return HealthResponse(status="ok", chunks_loaded=chunks_loaded)


@router.get("/stats", response_model=StatsResponse)
async def stats(request: Request) -> StatsResponse:
    """Usage statistics."""
    sessions = _get_sessions(request)
    return StatsResponse(active_conversations=len(sessions))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse | JSONResponse:
    """Answer a question using the RAG agent (with optional conversation history)."""
    agent, _, chunks_by_id, chunks_loaded = _get_state(request)
    if agent is None or chunks_loaded == 0:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service unavailable: chunks not loaded or agent not initialized."},
        )
    sessions = _get_sessions(request)
    conversation_id = body.conversation_id or "default"
    memory = sessions.get(conversation_id)
    if memory is None:
        memory = ConversationMemory(max_turns=10)
        sessions[conversation_id] = memory
    history = memory.get_history()
    resp = await asyncio.to_thread(agent.answer, body.query, history)
    memory.add_turn(body.query, resp.answer, resp.sources_used)
    chunks_used = []
    for cid in resp.sources_used:
        chunk = chunks_by_id.get(cid)
        if chunk:
            chunks_used.append(
                ChunkSummary(
                    id=chunk.id,
                    header_path=chunk.header_path,
                    snippet=(chunk.text[:300] + "…") if len(chunk.text) > 300 else chunk.text,
                )
            )
        else:
            chunks_used.append(ChunkSummary(id=cid, header_path="", snippet=""))
    citations = [
        CitationOut(index=c.index, chunk_id=c.chunk_id, snippet=c.snippet)
        for c in resp.citations
    ]
    return ChatResponse(
        answer=resp.answer,
        citations=citations,
        chunks_used=chunks_used,
        confidence=0.0,
    )


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(request: Request, body: SearchRequest) -> SearchResponse | JSONResponse:
    """Direct search (no generation)."""
    _, retriever, chunks_by_id, chunks_loaded = _get_state(request)
    if retriever is None or chunks_loaded == 0:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service unavailable: chunks not loaded or retriever not initialized."},
        )
    results = await asyncio.to_thread(retriever.search, body.query, body.top_k)
    hits = []
    for r in results:
        chunk = r.chunk
        hits.append(
            SearchHit(
                chunk_id=chunk.id,
                header_path=chunk.header_path,
                text=chunk.text[:500] + "…" if len(chunk.text) > 500 else chunk.text,
                score=round(r.score, 4),
            )
        )
    return SearchResponse(query=body.query, results=hits)


@router.delete("/conversation")
async def clear_conversation(request: Request, conversation_id: str = "default") -> dict:
    """Clear conversation history for the given conversation_id."""
    sessions = _get_sessions(request)
    if conversation_id in sessions:
        sessions[conversation_id].clear()
    return {"ok": True, "conversation_id": conversation_id}
