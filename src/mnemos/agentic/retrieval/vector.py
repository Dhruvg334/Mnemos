"""Vector retriever with date, revision, and permission filters."""

from __future__ import annotations

import asyncio
import math
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.services.llm import LLMService
from mnemos.core.errors import AppError
from mnemos.models.vector import ChunkEmbedding, DocumentChunk

try:
    import openai
except Exception:
    openai = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

import requests


class VectorSearchResult(BaseModel):
    content: str
    metadata: dict[str, Any]
    score: float
    document_id: str | None = None
    chunk_id: str | None = None


class VectorRetriever:
    """Semantic search via embeddings with multi-provider support.

    Generates embeddings using HuggingFace / OpenAI / Ollama and ranks
    candidate evidence regions by cosine similarity.

    Supports:
    - Site/organisation permission filtering
    - Date range filtering
    - Asset ID scoping
    - Document ID scoping
    - pgvector-based production search
    """

    def __init__(
        self,
        db: AsyncSession,
        llm_service: LLMService | None = None,
    ):
        self.db = db
        self.llm = llm_service
        self.provider = os.getenv("MNEMOS_AI_PROVIDER", "huggingface").lower()
        self.hf_model = os.getenv(
            "MNEMOS_HF_EMBEDDING_MODEL",
            "sentence-transformers/all-mpnet-base-v2",
        )
        self.openai_model = os.getenv(
            "MNEMOS_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.ollama_model = os.getenv("MNEMOS_OLLAMA_EMBEDDING_MODEL", "bge-mini")
        self._hf_client: SentenceTransformer | None = None
        self._executor = ThreadPoolExecutor(max_workers=2)

    # ------------------------------------------------------------------
    # Embedding generation
    # ------------------------------------------------------------------

    async def _ensure_hf(self) -> None:
        if self._hf_client is None and SentenceTransformer is not None:
            loop = asyncio.get_event_loop()
            self._hf_client = await loop.run_in_executor(
                self._executor, SentenceTransformer, self.hf_model
            )

    async def get_embeddings(self, text: str) -> list[float]:
        """Generate an embedding vector for *text* using the configured provider."""
        if not text:
            return []

        if self.llm is not None:
            embedding = await self.llm.get_embeddings(text)
            if not embedding:
                raise AppError(
                    "EMBEDDING_GENERATION_FAILED",
                    "An embedding could not be generated.",
                    502,
                )
            return embedding

        if self.provider == "huggingface":
            if SentenceTransformer is None:
                raise RuntimeError(
                    "sentence-transformers not available for HuggingFace embeddings"
                )
            await self._ensure_hf()
            loop = asyncio.get_event_loop()
            emb = await loop.run_in_executor(
                self._executor, self._hf_client.encode, text, True
            )
            return list(map(float, emb.tolist() if hasattr(emb, "tolist") else emb))

        if self.provider == "openai":
            if openai is None:
                raise RuntimeError("openai package not installed")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required")
            openai.api_key = api_key
            model = self.openai_model

            def _call() -> list[float]:
                resp = openai.Embedding.create(input=text, model=model)
                return resp["data"][0]["embedding"]

            loop = asyncio.get_event_loop()
            return list(map(float, await loop.run_in_executor(self._executor, _call)))

        if self.provider == "ollama":
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            resp = requests.post(
                f"{ollama_url}/api/embeddings",
                json={"model": self.ollama_model, "input": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("data", [{}])[0].get("embedding")
            if not emb:
                raise RuntimeError("No embedding in Ollama response")
            return list(map(float, emb))

        raise RuntimeError(f"Unknown MNEMOS_AI_PROVIDER: {self.provider}")

    # ------------------------------------------------------------------
    # Similarity search
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        lena = math.sqrt(sum(x * x for x in a))
        lenb = math.sqrt(sum(x * x for x in b))
        if lena == 0 or lenb == 0:
            return 0.0
        return dot / (lena * lenb)

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        if not query_embedding:
            return []

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
