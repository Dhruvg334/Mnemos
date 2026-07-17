"""Agent interfaces for the multi-agent runtime.

Defines the protocol that all agents must implement to participate
in the collaborative investigation workflow.  Agents communicate only
through the shared ``InvestigationState`` and typed messages.
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
    """Abstract base class for all agents in the system.

    Every agent must implement:
    - ``name``: unique identifier
    - ``registration``: registry metadata describing capabilities
    - ``run()``: the agent's execution logic
    """

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
        """Execute the agent's logic given the current state.

        Returns the updated state.  Agents must never directly call
        databases; they communicate only through the shared state
        and typed messages.
        """

    async def as_function(
        self, state: dict[str, Any]
    ) -> dict[str, Any]:
        """Adapter that allows this agent to be used as a plain async
        callable in the runtime workflow.

        Bridges between the ``AgentState`` TypedDict used by legacy
        code and the plain ``dict`` used by the runtime.
        """
        result_state = await self.run(state)
        return dict(result_state)


class ToolCallingAgent(BaseAgent):
    """Interface for agents that can interact with external tools.

    Tools are invoked through the runtime's tool registry, not
    directly by the agent.  This interface provides the structural
    contract for tool invocation tracking.
    """

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a specific tool and return its result."""


class CollaborativeAgent(BaseAgent):
    """Interface for agents that participate in collaborative execution.

    These agents can:
    - Emit typed messages to other agents
    - Request replanning from the supervisor
    - Declare what evidence they need and produce
    """

    @property
    def required_capabilities(self) -> list[str]:
        """Capabilities this agent needs from other agents."""
        return []

    @property
    def produced_capabilities(self) -> list[str]:
        """Capabilities this agent produces for other agents."""
        return []

    def to_registration(self) -> AgentRegistration:
        """Build an ``AgentRegistration`` from this agent's metadata."""
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
