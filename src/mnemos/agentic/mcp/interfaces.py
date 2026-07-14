from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPResource(BaseModel):
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class BaseMCPClient(ABC):
    """
    Interface for Model Context Protocol (MCP) interactions.
    Allows the agent to discover and use external tools and resources.
    """

    @abstractmethod
    async def list_tools(self) -> List[ToolDefinition]:
        """List available tools from the MCP server."""
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool via MCP."""
        pass

    @abstractmethod
    async def list_resources(self) -> List[MCPResource]:
        """List available data resources."""
        pass

    @abstractmethod
    async def read_resource(self, uri: str) -> str:
        """Read content from a specific resource URI."""
        pass
