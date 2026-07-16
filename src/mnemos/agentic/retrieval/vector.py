from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.deps import get_llm_service
from mnemos.agentic.services.llm import LLMService


class VectorSearchResult(BaseModel):
    content: str
    metadata: dict[str, Any]
    score: float
    document_id: str
    chunk_id: str

class VectorRetriever:
    """
    Handles semantic search using pgvector or a similar vector store.
    Supports filtering by site_id and org_id.
    """
    def __init__(self, db: AsyncSession, llm_service: LLMService | None = None):
        self.db = db
        self.llm = llm_service or get_llm_service()

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[VectorSearchResult]:
        """
        Executes a vector similarity search.
        In production, this queries a table with a 'vector' column.
        """
        # Placeholder for actual pgvector query
        # Example SQL:
        # SELECT content, metadata, 1 - (embedding <=> :embedding) as score
        # FROM document_chunks
        # WHERE site_id = :site_id
        # ORDER BY embedding <=> :embedding
        # LIMIT :limit

        try:
            # Build base query using pgvector's '<=>'
            where_clauses = ["true"]
            params: dict[str, Any] = {"embedding": query_embedding, "limit": top_k}
            
            if filters:
                if filters.get("tenant_id"):
                    where_clauses.append("tenant_id = :tenant_id")
                    params["tenant_id"] = filters.get("tenant_id")
                if filters.get("site_id"):
                    where_clauses.append("site_id = :site_id")
                    params["site_id"] = filters.get("site_id")
                if filters.get("asset_id"):
                    where_clauses.append("asset_id = :asset_id")
                    params["asset_id"] = filters.get("asset_id")
                if filters.get("revision_id"):
                    where_clauses.append("revision_id = :revision_id")
                    params["revision_id"] = filters.get("revision_id")
                if filters.get("metadata"):
                    # Assuming metadata is a dict we want to match as JSONB contains
                    for k, v in filters["metadata"].items():
                        where_clauses.append(f"metadata @> '{{\"{k}\": \"{v}\"}}'")

            where_sql = " AND ".join(where_clauses)

            sql = text(
                "SELECT id as chunk_id, content, metadata, document_id, "
                "1 - (embedding <=> :embedding) as score "
                f"FROM document_chunks WHERE {where_sql} "
                "ORDER BY embedding <=> :embedding LIMIT :limit"
            )

            result = await self.db.execute(sql, params)
            rows = result.fetchall()
            out: list[VectorSearchResult] = []
            for r in rows:
                out.append(VectorSearchResult(
                    content=r["content"],
                    metadata=r["metadata"] or {},
                    score=float(r["score"]),
                    document_id=r["document_id"],
                    chunk_id=r["chunk_id"]
                ))
            return out
        except Exception:
            # If DB or table isn't available, return empty list rather than crashing
            return []

    async def get_embeddings(self, text: str) -> list[float]:
        """
        Interfaces with an embedding model (OpenAI, HuggingFace, etc.)
        """
        return await self.llm.get_embeddings(text)
