from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.providers import get_llm_service
from mnemos.agentic.services.llm import LLMService
from mnemos.core.errors import AppError
from mnemos.models.vector import ChunkEmbedding, DocumentChunk


class VectorSearchResult(BaseModel):
    content: str
    metadata: dict[str, Any]
    score: float
    document_id: str
    chunk_id: str


class VectorRetriever:
    """
    Site- and tenant-scoped semantic retrieval over pgvector.
    """

    def __init__(
        self,
        db: AsyncSession,
        llm_service: LLMService | None = None,
    ):
        self.db = db
        self.llm = llm_service or get_llm_service()

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        if not query_embedding:
            raise AppError(
                "EMBEDDING_GENERATION_FAILED",
                "A query embedding could not be generated.",
                502,
            )

        top_k = max(1, min(top_k, 100))
        filters = filters or {}

        conditions = []
        if tenant_id := filters.get("tenant_id"):
            conditions.append(DocumentChunk.tenant_id == tenant_id)
        if site_id := filters.get("site_id"):
            conditions.append(DocumentChunk.site_id == site_id)
        if asset_id := filters.get("asset_id"):
            conditions.append(DocumentChunk.asset_id == asset_id)
        if revision_id := filters.get("revision_id"):
            conditions.append(
                DocumentChunk.revision_id == revision_id
            )

        metadata_filter = filters.get("metadata")
        if metadata_filter:
            conditions.append(
                DocumentChunk.metadata_json.contains(metadata_filter)
            )

        distance = ChunkEmbedding.embedding.cosine_distance(
            query_embedding
        )
        statement = (
            select(
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.content,
                DocumentChunk.metadata_json.label("metadata"),
                DocumentChunk.document_id,
                (1 - distance).label("score"),
            )
            .join(
                ChunkEmbedding,
                ChunkEmbedding.chunk_id == DocumentChunk.id,
            )
            .where(and_(*conditions) if conditions else True)
            .order_by(distance)
            .limit(top_k)
        )

        try:
            rows = (await self.db.execute(statement)).mappings().all()
        except (OperationalError, DBAPIError) as exc:
            raise AppError(
                "VECTOR_STORE_UNAVAILABLE",
                "Semantic retrieval is temporarily unavailable.",
                503,
                retryable=True,
            ) from exc
        except ValueError as exc:
            raise AppError(
                "EMBEDDING_DIMENSION_MISMATCH",
                "The embedding configuration is incompatible "
                "with the vector index.",
                500,
            ) from exc

        return [
            VectorSearchResult(
                content=row["content"],
                metadata=row["metadata"] or {},
                score=float(row["score"]),
                document_id=row["document_id"],
                chunk_id=row["chunk_id"],
            )
            for row in rows
        ]

    async def get_embeddings(self, text: str) -> list[float]:
        embedding = await self.llm.get_embeddings(text)
        if not embedding:
            raise AppError(
                "EMBEDDING_GENERATION_FAILED",
                "An embedding could not be generated.",
                502,
            )
        return embedding
