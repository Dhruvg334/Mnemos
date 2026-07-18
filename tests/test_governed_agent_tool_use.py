"""Tests for bounded, scoped agent tool use and trajectory recording."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.agents.retrieval.query_router import (
    QueryClassification,
    QueryRouterAgent,
)
from mnemos.agentic.agents.tool_runtime import (
    MAX_TOOL_CALLS_PER_AGENT,
    execute_governed_tool,
)
from mnemos.agentic.schemas.base import MCPToolResult, QueryIntent


class _FakeToolServer:
    def __init__(self, result: MCPToolResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def call(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


@pytest.mark.asyncio
async def test_governed_tool_call_preserves_scope_and_records_trajectory() -> None:
    server = _FakeToolServer(
        MCPToolResult(
            tool_name="resolve_asset_tag",
            success=True,
            data={"resolved": True, "entities": []},
        )
    )
    state = {
        "investigation_id": "inv-1",
        "trace_id": "trace-1",
        "context": {
            "org_id": "org-1",
            "site_id": "site-1",
            "user_id": "user-1",
            "role": "reliability_engineer",
            "access_classifications": ["internal"],
            "asset_ids": ["asset-1"],
            "document_ids": ["doc-1"],
        },
    }

    result = await execute_governed_tool(
        agent_name="query_router",
        server=server,
        tool_name="resolve_asset_tag",
        arguments={"mention": "P-101", "site_id": "site-1"},
        state=state,
    )

    assert result["resolved"] is True
    assert server.calls[0]["user_context"]["org_id"] == "org-1"
    assert server.calls[0]["user_context"]["site_id"] == "site-1"
    trajectory = state["context"]["tool_trajectory"]
    assert trajectory[0]["agent_name"] == "query_router"
    assert trajectory[0]["tool_name"] == "resolve_asset_tag"
    assert trajectory[0]["success"] is True


@pytest.mark.asyncio
async def test_governed_tool_call_enforces_agent_budget() -> None:
    server = _FakeToolServer(
        MCPToolResult(tool_name="resolve_asset_tag", success=True, data={})
    )
    state = {
        "context": {"tool_call_counts": {"query_router": MAX_TOOL_CALLS_PER_AGENT}}
    }

    result = await execute_governed_tool(
        agent_name="query_router",
        server=server,
        tool_name="resolve_asset_tag",
        arguments={"mention": "P-101"},
        state=state,
    )

    assert result["success"] is False
    assert "budget exhausted" in result["error"]
    assert server.calls == []


@pytest.mark.asyncio
async def test_query_router_resolves_entities_through_governed_tool() -> None:
    db = MagicMock(spec=AsyncSession)
    agent = QueryRouterAgent(db)
    agent.llm = MagicMock()
    agent.llm.call_structured = AsyncMock(
        return_value=QueryClassification(
            intent=QueryIntent.RCA,
            entities=["P-101"],
            confidence=0.93,
        )
    )
    server = _FakeToolServer(
        MCPToolResult(
            tool_name="resolve_asset_tag",
            success=True,
            data={
                "resolved": True,
                "entities": [
                    {
                        "entity_id": "asset-p101",
                        "canonical_name": "P-101",
                        "entity_type": "asset",
                        "confidence": 0.98,
                        "metadata": {"site_id": "site-1"},
                    }
                ],
            },
        )
    )
    agent.set_mcp_server(server)
    state = {
        "investigation_id": "inv-1",
        "query": "Why did P-101 fail?",
        "context": {"org_id": "org-1", "site_id": "site-1"},
    }

    result = await agent.execute(state)

    resolved = result["context"]["resolved_entities"]
    assert len(resolved) == 1
    assert resolved[0].entity_id == "asset-p101"
    assert server.calls[0]["tool_name"] == "resolve_asset_tag"
    assert result["context"]["tool_trajectory"][0]["success"] is True
