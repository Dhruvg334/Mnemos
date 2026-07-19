from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mnemos.core import neo4j
from mnemos.core.config import settings
from mnemos.services.operations.health import assess_readiness


@pytest.mark.asyncio
async def test_optional_neo4j_failure_does_not_abort_startup(monkeypatch) -> None:
    driver = MagicMock()
    driver.verify_connectivity = AsyncMock(side_effect=ConnectionError("offline"))
    driver.close = AsyncMock()

    monkeypatch.setattr(settings, "neo4j_enabled", True)
    monkeypatch.setattr(settings, "neo4j_startup_required", False)
    monkeypatch.setattr(settings, "neo4j_connect_timeout_seconds", 0.1)
    monkeypatch.setattr(neo4j, "_driver", driver)

    status = await neo4j.init_neo4j()

    assert status == "unavailable"
    assert neo4j.get_neo4j_state().status == "unavailable"
    driver.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_required_neo4j_failure_aborts_startup(monkeypatch) -> None:
    driver = MagicMock()
    driver.verify_connectivity = AsyncMock(side_effect=ConnectionError("offline"))
    driver.close = AsyncMock()

    monkeypatch.setattr(settings, "neo4j_enabled", True)
    monkeypatch.setattr(settings, "neo4j_startup_required", True)
    monkeypatch.setattr(settings, "neo4j_connect_timeout_seconds", 0.1)
    monkeypatch.setattr(neo4j, "_driver", driver)

    with pytest.raises(neo4j.Neo4jUnavailableError):
        await neo4j.init_neo4j()

    assert neo4j.get_neo4j_state().status == "unavailable"


def test_optional_neo4j_outage_degrades_but_keeps_readiness(monkeypatch) -> None:
    monkeypatch.setattr(settings, "external_health_checks_enabled", False)
    monkeypatch.setattr(settings, "neo4j_required_for_readiness", False)

    ready, status = assess_readiness(
        {
            "database": "healthy",
            "pgvector": "healthy",
            "redis": "disabled",
            "object_storage": "disabled",
            "neo4j": "unavailable",
        }
    )

    assert ready is True
    assert status == "degraded"


def test_required_neo4j_outage_fails_readiness(monkeypatch) -> None:
    monkeypatch.setattr(settings, "external_health_checks_enabled", False)
    monkeypatch.setattr(settings, "neo4j_required_for_readiness", True)

    ready, status = assess_readiness(
        {
            "database": "healthy",
            "pgvector": "healthy",
            "redis": "disabled",
            "object_storage": "disabled",
            "neo4j": "unavailable",
        }
    )

    assert ready is False
    assert status == "unhealthy"
