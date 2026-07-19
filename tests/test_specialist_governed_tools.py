"""Tests for resilient governed specialist tool execution."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mnemos.agentic.agents.reasoning.tool_enrichment import scoped_asset_ids
from mnemos.agentic.agents.tool_runtime import execute_governed_tool


class _ExplodingServer:
    call = AsyncMock(side_effect=RuntimeError("provider secret must not leak"))


@pytest.mark.asyncio
async def test_tool_boundary_records_safe_failure_without_raising() -> None:
    state = {"investigation_id": "inv-1", "context": {"org_id": "org-1"}}

    result = await execute_governed_tool(
        agent_name="rca_agent",
        server=_ExplodingServer(),
        tool_name="similar_failures",
        arguments={"asset_id": "asset-1"},
        state=state,
    )

    assert result["success"] is False
    assert "RuntimeError" in result["error"]
    assert "provider secret" not in result["error"]
    trajectory = state["context"]["tool_trajectory"]
    assert trajectory[0]["success"] is False
    assert trajectory[0]["tool_name"] == "similar_failures"


def test_scoped_asset_ids_are_deduplicated_and_bounded() -> None:
    state = {
        "context": {
            "asset_ids": ["asset-1", "asset-2", "asset-1"],
            "resolved_entities": [{"entity_id": "asset-3"}],
        }
    }

    assert scoped_asset_ids(state, [], limit=2) == ["asset-1", "asset-2"]
