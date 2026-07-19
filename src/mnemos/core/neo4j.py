from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from neo4j import AsyncDriver, AsyncGraphDatabase

from mnemos.core.config import settings
from mnemos.core.logging import get_logger

logger = get_logger("neo4j")

_driver: AsyncDriver | None = None


class Neo4jUnavailableError(RuntimeError):
    """Raised when graph access is disabled or currently unavailable."""


@dataclass(slots=True)
class Neo4jConnectionState:
    status: str = "not_initialized"
    detail: str | None = None


_state = Neo4jConnectionState()


def get_neo4j_state() -> Neo4jConnectionState:
    """Return a copy of the current graph connection state."""
    return Neo4jConnectionState(status=_state.status, detail=_state.detail)


def _set_state(status: str, detail: str | None = None) -> None:
    _state.status = status
    _state.detail = detail


def get_driver() -> AsyncDriver:
    """Return the shared driver, creating it lazily when graph support is enabled."""
    global _driver
    if not settings.neo4j_enabled:
        _set_state("disabled")
        raise Neo4jUnavailableError("Neo4j integration is disabled")

    if _driver is None:
        logger.info("Creating Neo4j driver for %s", settings.neo4j_uri)
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            max_connection_pool_size=settings.neo4j_max_connection_pool_size,
            connection_timeout=settings.neo4j_connect_timeout_seconds,
            keep_alive=True,
        )
    return _driver


async def init_neo4j() -> str:
    """Probe Neo4j without taking down the API when graph support is optional."""
    if not settings.neo4j_enabled:
        _set_state("disabled")
        logger.info("Neo4j integration is disabled")
        return "disabled"

    try:
        driver = get_driver()
        await asyncio.wait_for(
            driver.verify_connectivity(),
            timeout=settings.neo4j_connect_timeout_seconds,
        )
    except Exception as exc:
        _set_state("unavailable", type(exc).__name__)
        await close_neo4j(preserve_state=True)
        logger.warning(
            "Neo4j is unavailable during startup; graph-dependent features will be degraded",
        )
        if settings.neo4j_startup_required:
            raise Neo4jUnavailableError("Required Neo4j startup probe failed") from exc
        return "unavailable"

    _set_state("healthy")
    logger.info("Neo4j connectivity verified")
    return "healthy"


async def close_neo4j(*, preserve_state: bool = False) -> None:
    global _driver
    if _driver is not None:
        driver, _driver = _driver, None
        try:
            await driver.close()
        except Exception:
            logger.warning("Neo4j driver close failed")
        else:
            logger.info("Neo4j connection closed")
    if not preserve_state:
        _set_state("disabled" if not settings.neo4j_enabled else "not_initialized")


async def check_neo4j_health() -> str:
    """Perform a bounded graph probe and update the shared connection state."""
    if not settings.neo4j_enabled:
        _set_state("disabled")
        return "disabled"

    try:
        driver = get_driver()
        await asyncio.wait_for(
            driver.verify_connectivity(),
            timeout=settings.neo4j_connect_timeout_seconds,
        )
    except Exception as exc:
        _set_state("unavailable", type(exc).__name__)
        await close_neo4j(preserve_state=True)
        logger.warning("Neo4j health probe failed")
        return "unavailable"

    _set_state("healthy")
    return "healthy"


async def get_neo4j_session() -> AsyncIterator:
    """FastAPI dependency for yielding Neo4j sessions."""
    driver = get_driver()
    async with driver.session() as session:
        yield session
