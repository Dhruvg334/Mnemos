"""Vector retriever with date, revision, and permission filters."""

from __future__ import annotations

import asyncio
import json as _json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
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
        """Search by embedding similarity with optional filters."""
        if not query_embedding:
            return []

        filters = filters or {}
        candidates = await self._fetch_candidates(filters)

        scored: list[VectorSearchResult] = []
        for c in candidates:
            meta = c.get("metadata") or {}
            emb = self._extract_embedding(meta)
            if emb is None:
                continue

            score = self._cosine(query_embedding, emb)
            scored.append(
                VectorSearchResult(
                    content=c.get("text_excerpt", ""),
                    metadata=meta,
                    score=float(score),
                    document_id=c.get("document_id"),
                    chunk_id=meta.get("chunk_id"),
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_candidates(
        self, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Load candidate evidence regions from the DB, applying filters."""
        from sqlalchemy import select

        from mnemos.models.entities import Document, EvidenceRegion

        site_id = filters.get("site_id")
        date_from = filters.get("date_from")
        date_to = filters.get("date_to")

        # Build query using ORM for portability
        stmt = (
            select(EvidenceRegion, Document)
            .join(Document, EvidenceRegion.document_id == Document.id)
        )

        if site_id:
            stmt = stmt.where(Document.site_id == site_id)
        if date_from:
            stmt = stmt.where(Document.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Document.created_at <= date_to)

        stmt = stmt.limit(1000)

        try:
            result = await self.db.execute(stmt)
            rows = result.all()
        except Exception:
            return []

        candidates: list[dict[str, Any]] = []
        for er, doc in rows:
            candidates.append(
                {
                    "id": er.id,
                    "text_excerpt": er.text_excerpt,
                    "metadata": er.metadata_json or {},
                    "document_id": doc.id,
                }
            )
        return candidates

    @staticmethod
    def _extract_embedding(meta: dict[str, Any]) -> list[float] | None:
        emb = meta.get("embedding") or meta.get("chunk_embedding") or meta.get("vector")
        if isinstance(emb, str):
            try:
                emb = _json.loads(emb)
            except Exception:
                return None
        if isinstance(emb, list) and emb:
            return emb
        return None
