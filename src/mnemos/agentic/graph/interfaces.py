from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    properties: dict[str, Any] = {}


class GraphRelationship(BaseModel):
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = {}


class GraphQueryResult(BaseModel):
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]
    metadata: dict[str, Any] = {}


class BaseGraphClient(ABC):
    """
    Abstract interface for interacting with the Knowledge Graph (Neo4j).
    """

    @abstractmethod
    async def query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a raw Cypher query."""
        pass

    @abstractmethod
    async def get_asset_context(self, asset_id: str, depth: int = 2) -> GraphQueryResult:
        """Retrieve the neighborhood of an asset in the graph."""
        pass

    @abstractmethod
    async def find_related_failures(self, asset_id: str) -> list[GraphNode]:
        """Find historical failure events related to an asset or its components."""
        pass
