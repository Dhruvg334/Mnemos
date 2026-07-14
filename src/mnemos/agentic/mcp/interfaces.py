from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPResource(BaseModel):
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None


class BaseMCPClient(ABC):
    """
    Interface for Model Context Protocol (MCP) interactions.
    Allows the agent to discover and use external tools and resources.
    """

    @abstractmethod
    async def list_tools(self) -> list[ToolDefinition]:
        """List available tools from the MCP server."""
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool via MCP."""
        pass

    @abstractmethod
    async def list_resources(self) -> list[MCPResource]:
        """List available data resources."""
        pass

    @abstractmethod
    async def read_resource(self, uri: str) -> str:
        """Read content from a specific resource URI."""
        pass
