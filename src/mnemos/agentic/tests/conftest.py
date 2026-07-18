"""Shared fixtures and configuration for agentic layer tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mnemos.core.db import Base


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration-db-url",
        action="store",
        default=None,
        help="PostgreSQL URL for integration tests (e.g. postgresql+asyncpg://...)",
    )


@pytest_asyncio.fixture
async def in_memory_db() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """In-memory SQLite database for unit tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(in_memory_db) -> AsyncGenerator[AsyncSession, None]:
    async with in_memory_db() as session:
        yield session
