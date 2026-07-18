from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class RetrievalQuery(BaseModel):
    text: str
    filters: dict[str, Any] = {}
    top_k: int = 5
    site_id: str | None = None
    org_id: str | None = None


class RetrievalResult(BaseModel):
    content: str
    metadata: dict[str, Any]
    score: float
    source_id: str


class BaseRetriever(ABC):
    """
    Abstract base class for all retrieval engines (Vector, Graph, SQL).
    """

    @abstractmethod
    async def retrieve(self, query: RetrievalQuery) -> list[RetrievalResult]:
        """Retrieve relevant information based on the query."""
        pass
