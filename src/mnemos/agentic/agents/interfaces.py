"""Agent interfaces for the multi-agent runtime.

Defines the protocol that all agents must implement to participate
in the collaborative investigation workflow.  Agents communicate only
through the shared ``InvestigationState`` and typed messages.

P0 #13: Dynamic tool selection — agents inspect state, discover permitted
tools via their allowlist, choose the correct tool, execute it via the
MCP dispatch layer, and change strategy based on results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mnemos.agentic.runtime.types import (
    AgentCapability,
    AgentRegistration,
    AgentRole,
)
from mnemos.agentic.schemas.state import AgentState


class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique identifier for the agent."""

    @property
    @abstractmethod
    def registration(self) -> AgentRegistration:
        """Return the registry metadata for this agent."""

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Execute the agent's logic given the current state."""

    async def as_function(self, state: dict[str, Any]) -> dict[str, Any]:
        result_state = await self.run(state)
        return dict(result_state)


class ToolCallingAgent(BaseAgent):
    """Interface for agents that can invoke tools via the MCP dispatch layer (P0 #13).

    Agents do NOT call databases directly.  They call tools through
    ``call_tool()``, which enforces allowlists, guardrails, and audit logging.
    """

    _mcp_server: Any = None  # injected at orchestration time

    def set_mcp_server(self, server: Any) -> None:
        """Inject the MCP server (called by orchestrator or pipeline)."""
        self._mcp_server = server

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a tool via the MCP dispatch layer.

        P0 #13: The agent inspects the current workflow state to determine
        which tool to call and what arguments to pass.  The call goes through
        the allowlist check, guardrail policy, and audit log before execution.
        """
        if self._mcp_server is None:
            return {"success": False, "error": "MCP server not available"}

        investigation_id = ""
        trace_id = None
        user_context: dict[str, Any] = {}
        if state:
            investigation_id = state.get("investigation_id", "")
            trace_id = state.get("trace_id")
            ctx = state.get("context", {})
            user_context = {
                "org_id": ctx.get("org_id", ""),
                "site_id": ctx.get("site_id", ""),
                "user_id": ctx.get("user_id", ""),
                "role": ctx.get("role", "engineer"),
                "access_classifications": ctx.get("access_classifications", ["internal"]),
                "asset_ids": ctx.get("asset_ids", []),
                "document_ids": ctx.get("document_ids", []),
            }

        result = await self._mcp_server.call(
            tool_name=tool_name,
            arguments=arguments,
            agent_name=self.name,
            investigation_id=investigation_id,
            trace_id=trace_id,
            user_context=user_context,
        )
        # Return the data payload or the full result for callers to inspect
        if hasattr(result, "data") and result.success:
            return result.data
        if hasattr(result, "error"):
            return {"success": False, "error": result.error}
        return result

    def discover_permitted_tools(self) -> frozenset[str]:
        """Return the set of tools this agent is permitted to call (P0 #13)."""
        try:
            from mnemos.agentic.mcp.dispatch import _AGENT_TOOL_ALLOWLISTS
            return _AGENT_TOOL_ALLOWLISTS.get(self.name, frozenset())
        except ImportError:
            return frozenset()

    @abstractmethod
    async def call_tool(  # type: ignore[override]
        self, tool_name: str, arguments: dict[str, Any],
        *, state: dict[str, Any] | None = None,
    ) -> Any: ...


class CollaborativeAgent(BaseAgent):
    """Interface for agents that participate in collaborative execution."""

    @property
    def required_capabilities(self) -> list[str]:
        return []

    @property
    def produced_capabilities(self) -> list[str]:
        return []

    def to_registration(self) -> AgentRegistration:
        return AgentRegistration(
            name=self.name,
            role=AgentRole.GENERIC,
            capabilities=[
                AgentCapability(
                    name=self.name,
                    input_types=self.required_capabilities,
                    output_types=self.produced_capabilities,
                )
            ],
        )
