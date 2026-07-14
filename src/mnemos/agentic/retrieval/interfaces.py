from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class RetrievalQuery(BaseModel):
    text: str
    filters: Dict[str, Any] = {}
    top_k: int = 5
    site_id: str | None = None
    org_id: str | None = None


class RetrievalResult(BaseModel):
    content: str
    metadata: Dict[str, Any]
    score: float
    source_id: str


class BaseRetriever(ABC):
    """
    Abstract base class for all retrieval engines (Vector, Graph, SQL).
    """

    @abstractmethod
    async def retrieve(self, query: RetrievalQuery) -> List[RetrievalResult]:
        """Retrieve relevant information based on the query."""
        pass


class HybridRetriever(BaseRetriever):
    """
    Interface for a retriever that combines multiple sources.
    """
    @abstractmethod
    async def rerank(self, results: List[RetrievalResult], query: str) -> List[RetrievalResult]:
        """Rerank results using a cross-encoder or similar logic."""
        pass
