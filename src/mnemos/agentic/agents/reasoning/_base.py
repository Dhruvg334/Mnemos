"""Shared base class for reasoning intelligence agents.

Provides common dependency injection, state management, and the
adapter pattern that bridges ``AgentState`` with the runtime.

All reasoning agents:
1. Read verified evidence from ``context["evidence_bundle"]``
2. Produce a ``ReasoningOutput`` stored in ``context["reasoning_output"]``
3. Never hallucinate facts — every claim must trace to verified evidence
4. Can request collaboration from other agents via ``next_recommended_agents``
5. Can call tools via the MCP dispatch layer (P0 #13)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.agents.interfaces import CollaborativeAgent, ToolCallingAgent
from mnemos.agentic.deps import get_llm_service, get_prompt_manager
from mnemos.agentic.runtime.types import AgentRegistration, AgentRole
from mnemos.agentic.schemas.base import EvidenceBundle, ReasoningOutput
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.guardrails import MnemosGuardrails
from mnemos.agentic.utils.logging import StructuredLogger


class _BaseReasoningAgent(CollaborativeAgent, ABC):
    """Abstract base for all reasoning intelligence agents.

    Provides:
    - Dependency injection for ``db``, ``llm``, ``prompt_manager``, ``guardrails``
    - Shared ``as_function()`` adapter for the runtime workflow
    - Abstract ``execute()`` for concrete agent logic
    - Common evidence extraction and output storage
    - Dynamic tool calling via ``call_tool()`` (P0 #13)
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = get_llm_service()
        self.prompt_manager = get_prompt_manager()
        self.guardrails = MnemosGuardrails()
        self.logger = StructuredLogger(f"agents.reasoning.{self.name}")
        self._mcp_server: Any = None  # injected via set_mcp_server()

    # ------------------------------------------------------------------
    # P0 #13: Dynamic tool calling
    # ------------------------------------------------------------------

    def set_mcp_server(self, server: Any) -> None:
        """Inject the MCP server so this agent can call tools."""
        self._mcp_server = server

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        state: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a tool via the MCP dispatch layer (P0 #13).

        The agent inspects the current workflow state to build the correct
        user_context (org_id, site_id, role, access_classifications) so
        the allowlist and guardrail checks receive the right scope.
        """
        if self._mcp_server is None:
            return {"success": False, "error": "MCP server not injected"}

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
                "access_classifications": ctx.get(
                    "access_classifications", ["internal"]
                ),
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
        if hasattr(result, "data") and getattr(result, "success", False):
            return result.data
        if hasattr(result, "error"):
            return {"success": False, "error": result.error}
        return result

    def discover_permitted_tools(self) -> frozenset[str]:
        """Return tools this agent is allowed to call (P0 #13)."""
        try:
            from mnemos.agentic.mcp.dispatch import _AGENT_TOOL_ALLOWLISTS
            return _AGENT_TOOL_ALLOWLISTS.get(self.name, frozenset())
        except ImportError:
            return frozenset()

    # ------------------------------------------------------------------
    # BaseAgent abstract property satisfies
    # ------------------------------------------------------------------

    @property
    def registration(self) -> AgentRegistration:
        return self.to_registration()

    # ------------------------------------------------------------------
    # CollaborativeAgent overrides
    # ------------------------------------------------------------------

    def to_registration(self) -> AgentRegistration:
        return AgentRegistration(
            name=self.name,
            role=self.role,
            description=self.description,
            capabilities=self._capabilities(),
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
            dependencies=self.required_dependencies,
        )

    # ------------------------------------------------------------------
    # BaseAgent protocol
    # ------------------------------------------------------------------

    async def run(self, state: AgentState) -> AgentState:
        try:
            updated = await self.execute(state)
            steps = list(updated.get("steps_completed", []))
            steps.append(self.name)
            updated["steps_completed"] = steps
            return updated
        except Exception as exc:
            errors = list(state.get("errors", []))
            errors.append(f"AGENT_ERROR:{self.name}: {exc}")
            state["errors"] = errors
            return state

    async def as_function(self, state: dict[str, Any]) -> dict[str, Any]:
        result_state = await self.run(state)
        return dict(result_state)

    # ------------------------------------------------------------------
    # Evidence helpers
    # ------------------------------------------------------------------

    def _get_evidence_bundle(self, state: AgentState) -> EvidenceBundle | None:
        """Extract the verified evidence bundle from state."""
        ctx = state.get("context", {})
        return ctx.get("evidence_bundle")

    def _get_previous_reasoning(
        self, state: AgentState, agent_name: str | None = None
    ) -> list[ReasoningOutput]:
        """Extract previous reasoning outputs from state.

        If ``agent_name`` is given, filter to that agent only.
        """
        ctx = state.get("context", {})
        all_reasoning: list[ReasoningOutput] = ctx.get("reasoning_outputs", [])
        if agent_name:
            return [r for r in all_reasoning if r.agent_name == agent_name]
        return all_reasoning

    def _store_reasoning_output(
        self, state: AgentState, output: ReasoningOutput
    ) -> AgentState:
        """Store a reasoning output in state context."""
        ctx = dict(state.get("context", {}))
        outputs: list[ReasoningOutput] = ctx.get("reasoning_outputs", [])
        outputs.append(output)
        ctx["reasoning_outputs"] = outputs
        ctx["reasoning_output"] = output
        state["context"] = ctx
        return state

    def _validate_evidence_exists(
        self, state: AgentState
    ) -> EvidenceBundle | None:
        """Get evidence bundle or set abstain if missing."""
        bundle = self._get_evidence_bundle(state)
        if bundle is None:
            output = ReasoningOutput(
                agent_name=self.name,
                reasoning_decision="abstain",
                reasoning_summary="No evidence bundle available for reasoning",
            )
            self._store_reasoning_output(state, output)
        return bundle

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def _get_memory(self, state: AgentState):
        """Get the AgentMemory instance from state context."""
        ctx = state.get("context", {})
        return ctx.get("memory")

    def _record_memory(
        self,
        state: AgentState,
        memory_type,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        """Record a memory in the conversation buffer."""
        memory = self._get_memory(state)
        if memory is None:
            return None
        return memory.record(
            agent_name=self.name,
            memory_type=memory_type,
            content=content,
            metadata=metadata,
            tags=tags,
        )

    def _remember(
        self,
        state: AgentState,
        key: str,
        memory_type,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        """Store/update a working memory entry."""
        memory = self._get_memory(state)
        if memory is None:
            return None
        return memory.remember(
            key=key,
            agent_name=self.name,
            memory_type=memory_type,
            content=content,
            metadata=metadata,
            tags=tags,
        )

    def _recall(self, state: AgentState, key: str):
        """Retrieve a working memory entry."""
        memory = self._get_memory(state)
        if memory is None:
            return None
        return memory.recall(key)

    def _search_memory(
        self,
        state: AgentState,
        text: str | None = None,
        memory_type=None,
        limit: int = 10,
    ):
        """Search conversation memory."""
        memory = self._get_memory(state)
        if memory is None:
            return []
        return memory.search(text=text, memory_type=memory_type, limit=limit)

    # ------------------------------------------------------------------
    # Subclass hooks
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def role(self) -> AgentRole: ...

    @property
    def description(self) -> str:
        return ""

    @property
    def max_retries(self) -> int:
        return 2

    @property
    def timeout_seconds(self) -> float:
        return 120.0

    @property
    def required_dependencies(self) -> list[str]:
        return []

    @abstractmethod
    def _capabilities(self) -> list[Any]:
        return []

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState: ...
