from abc import ABC, abstractmethod
from typing import Any

from mnemos.agentic.schemas.state import AgentState


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    Follows the Interface Segregation Principle.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique identifier for the agent."""
        pass

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """
        Execute the agent's logic given the current state.
        Returns the updated state.
        """
        pass


class ToolCallingAgent(BaseAgent):
    """Interface for agents that can interact with external tools."""

    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a specific tool."""
        pass
