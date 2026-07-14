from typing import Any, Optional
import os
import math
import asyncio
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Optional integrations
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
    """
    Handles semantic search by:
      - Generating embeddings via configurable providers (HuggingFace / OpenAI / Ollama)
      - Retrieving candidate evidence from the relational DB and ranking by cosine similarity

    Strategy:
      - Fetch EvidenceRegion rows that contain stored embeddings in metadata (common ingestion pattern)
      - If DB-side vector search (pgvector) is available, that can be added later. For portability, this implementation
        reads stored embeddings from JSON metadata and computes cosine similarity in Python.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.provider = os.getenv("MNEMOS_AI_PROVIDER", "huggingface").lower()
        self.hf_model = os.getenv("MNEMOS_HF_EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
        self.openai_model = os.getenv("MNEMOS_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.ollama_model = os.getenv("MNEMOS_OLLAMA_EMBEDDING_MODEL", "bge-mini")
        self._hf_client: Optional[SentenceTransformer] = None
        # Thread pool for blocking model calls
        self._executor = ThreadPoolExecutor(max_workers=2)

    async def _ensure_hf(self):
        if self._hf_client is None and SentenceTransformer is not None:
            loop = asyncio.get_event_loop()
            self._hf_client = await loop.run_in_executor(self._executor, SentenceTransformer, self.hf_model)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        lena = math.sqrt(sum(x * x for x in a))
        lenb = math.sqrt(sum(x * x for x in b))
        if lena == 0 or lenb == 0:
            return 0.0
        return dot / (lena * lenb)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[VectorSearchResult]:
        """
        Performs a retrieval pass by loading candidate evidence regions from the relational DB
        and ranking by cosine similarity against the provided query_embedding.

        The implementation expects ingestion to store chunk/region embeddings in EvidenceRegion.metadata JSON
        under keys like 'embedding' or 'chunk_embedding'. If embeddings aren't available, this method returns empty.
        """
        if not query_embedding:
            return []

        site_id = filters.get("site_id") if filters else None

        # Fetch candidate evidence regions (limit to a reasonable candidate pool)
        stmt = select("evidence_regions.id", "evidence_regions.text_excerpt", "evidence_regions.metadata", "documents.id").select_from("evidence_regions").join("documents", "evidence_regions.document_id = documents.id")

        # Use raw SQL via SQLAlchemy text would be ideal, but keep portability using simple select of mapped entity is preferred.
        # Fall back to a conservative query: fetch recent or site-scoped evidence regions
        try:
            if site_id:
                # Note: using a simple query via text for flexibility
                from sqlalchemy import text
                sql = text(
                    "SELECT er.id as id, er.text_excerpt as text_excerpt, er.metadata as metadata, d.id as document_id "
                    "FROM evidence_regions er JOIN documents d ON er.document_id = d.id WHERE d.site_id = :site_id LIMIT 1000"
                )
                res = await self.db.execute(sql, {"site_id": site_id})
            else:
                from sqlalchemy import text
                sql = text(
                    "SELECT er.id as id, er.text_excerpt as text_excerpt, er.metadata as metadata, d.id as document_id "
                    "FROM evidence_regions er JOIN documents d ON er.document_id = d.id LIMIT 1000"
                )
                res = await self.db.execute(sql)
        except Exception:
            # As a last resort, try a simple mapped query using ORM models (keeps tests working)
            from mnemos.models.entities import EvidenceRegion, Document
            stmt2 = select(EvidenceRegion, Document).join(Document)
            if site_id:
                stmt2 = stmt2.where(Document.site_id == site_id).limit(1000)
            else:
                stmt2 = stmt2.limit(1000)
            result = await self.db.execute(stmt2)
            rows = result.all()

            candidates = []
            for er, doc in rows:
                candidates.append({
                    "id": er.id,
                    "text_excerpt": er.text_excerpt,
                    "metadata": er.metadata_json,
                    "document_id": doc.id
                })
        else:
            rows = res.mappings().all()
            candidates = []
            for r in rows:
                candidates.append({
                    "id": r.get("id"),
                    "text_excerpt": r.get("text_excerpt"),
                    "metadata": r.get("metadata") or {},
                    "document_id": r.get("document_id")
                })

        scored: list[VectorSearchResult] = []
        for c in candidates:
            meta = c.get("metadata") or {}
            emb = None
            if isinstance(meta, dict):
                emb = meta.get("embedding") or meta.get("chunk_embedding") or meta.get("vector")

            # If embedding stored as JSON string, try to parse
            if isinstance(emb, str):
                try:
                    import json as _json
                    emb = _json.loads(emb)
                except Exception:
                    emb = None

            if not emb:
                # skip candidates without stored embeddings
                continue

            score = self._cosine(query_embedding, emb)
            scored.append(VectorSearchResult(
                content=c.get("text_excerpt") or "",
                metadata=meta,
                score=float(score),
                document_id=c.get("document_id"),
                chunk_id=meta.get("chunk_id") or None
            ))

        # Sort by score desc and take top_k
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    async def get_embeddings(self, text: str) -> list[float]:
        """
        Generates an embedding vector for the provided text using the configured provider.
        Supported providers via MNEMOS_AI_PROVIDER: 'huggingface', 'openai', 'ollama'
        """
        if not text:
            return []

        provider = self.provider
        if provider == "huggingface":
            if SentenceTransformer is None:
                raise RuntimeError("sentence-transformers not available in environment for HuggingFace embeddings")
            await self._ensure_hf()
            loop = asyncio.get_event_loop()
            emb = await loop.run_in_executor(self._executor, self._hf_client.encode, text, True)
            # Ensure returned as list[float]
            return list(map(float, emb.tolist() if hasattr(emb, "tolist") else emb))

        elif provider == "openai":
            if openai is None:
                raise RuntimeError("openai package not installed")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings provider")
            openai.api_key = api_key
            model = self.openai_model
            # OpenAI embeddings API is blocking; run in thread
            def _call_openai():
                resp = openai.Embedding.create(input=text, model=model)
                return resp["data"][0]["embedding"]
            loop = asyncio.get_event_loop()
            emb = await loop.run_in_executor(self._executor, _call_openai)
            return list(map(float, emb))

        elif provider == "ollama":
            # Ollama local server expected at http://localhost:11434
            ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            model = self.ollama_model
            try:
                resp = requests.post(f"{ollama_url}/api/embeddings", json={"model": model, "input": text}, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                # Ollama embeddings response shape may vary; expect {'data': [{'embedding': [...] }]}
                emb = data.get("data", [{}])[0].get("embedding")
                if not emb:
                    raise RuntimeError("No embedding in Ollama response")
                return list(map(float, emb))
            except Exception as e:
                raise RuntimeError(f"Ollama embedding request failed: {e}")

        else:
            raise RuntimeError(f"Unknown MNEMOS_AI_PROVIDER: {provider}")
