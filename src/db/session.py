from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _get_database_url() -> str:
    """
    Return the async PostgreSQL database URL.

    Falls back to a sensible local default if not set, so tests and
    local development can run with minimal configuration.
    """
    return os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://csrag:csrag@localhost:5432/cs_rag",
    )


DATABASE_URL = _get_database_url()

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI-style dependency that yields an AsyncSession.

    Usage:
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session

