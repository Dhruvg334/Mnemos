"""Operational metrics and health diagnostics for governed tool execution."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from mnemos.agentic.agents.tool_metrics import tool_metrics
from mnemos.agentic.agents.tool_runtime import execute_governed_tool
from mnemos.agentic.schemas.base import MCPToolResult
from mnemos.main import app


class _Server:
    call = AsyncMock(
        return_value=MCPToolResult(tool_name="timeline", success=True, data={"events": []})
    )


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    tool_metrics.reset()


@pytest.mark.asyncio
async def test_governed_tool_records_operational_metrics() -> None:
    await execute_governed_tool(
        agent_name="evidence_retrieval",
        server=_Server(),
        tool_name="timeline",
        arguments={"asset_id": "asset-1"},
        state={"investigation_id": "inv-1", "context": {}},
    )

    snapshot = tool_metrics.snapshot(
        failure_rate_threshold=0.25,
        latency_threshold_ms=5_000,
    )
    assert snapshot["total_calls"] == 1
    assert snapshot["tools"]["timeline"]["successes"] == 1
    assert snapshot["tools"]["timeline"]["status"] == "healthy"


def test_tool_health_endpoint_reports_degraded_metrics() -> None:
    tool_metrics.record(
        tool_name="graph_traversal",
        success=False,
        duration_ms=25.0,
        failure_category="tool_error",
    )

    client = TestClient(app)
    response = client.get("/health/agent-tools")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["tools"]["graph_traversal"]["failure_categories"] == {
        "tool_error": 1
    }


def test_metrics_registry_keeps_bounded_latency_samples() -> None:
    for index in range(250):
        tool_metrics.record(tool_name="timeline", success=True, duration_ms=float(index))

    snapshot = tool_metrics.snapshot(
        failure_rate_threshold=0.25,
        latency_threshold_ms=10_000,
    )
    assert snapshot["tools"]["timeline"]["calls"] == 250
    assert snapshot["tools"]["timeline"]["p95_duration_ms"] >= 200
