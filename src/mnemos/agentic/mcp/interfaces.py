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
