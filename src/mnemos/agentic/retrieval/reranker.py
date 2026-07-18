import asyncio
import os
from abc import ABC, abstractmethod

from pydantic import BaseModel

# Prefer sentence_transformers CrossEncoder if available
try:
    from sentence_transformers import CrossEncoder
except Exception:
    CrossEncoder = None


class RerankResult(BaseModel):
    index: int
    score: float


class BaseReranker(ABC):
    """
    Abstract base class for reranking evidence.
    """
    @abstractmethod
    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]: ...


class CrossEncoderReranker(BaseReranker):
    """
    Cross-encoder reranker using BGE / CrossEncoder-style models.

    Behavior:
      - If sentence_transformers.CrossEncoder is available, use it for accurate pairwise scoring.
      - Otherwise fall back to a lightweight heuristic (word overlap + length-based) but this is NOT GPT reranking.

    The underlying model can be configured with MNEMOS_RERANKER_MODEL environment variable.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv("MNEMOS_RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        self._model: CrossEncoder | None = None
        # CrossEncoder initialization can be blocking; defer to first use

    async def _ensure_model(self):
        if self._model is None:
            if CrossEncoder is None:
                return
            loop = asyncio.get_event_loop()
            # instantiate in thread to avoid blocking event loop
            self._model = await loop.run_in_executor(None, CrossEncoder, self.model_name)

    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        if not documents:
            return []

        # Use CrossEncoder if available
        await self._ensure_model()
        if self._model is not None:
            # Build pairs (query, doc)
            pairs = [(query, d) for d in documents]
            loop = asyncio.get_event_loop()
            # The predict call is blocking; run in executor
            scores = await loop.run_in_executor(None, self._model.predict, pairs, None)
            # normalize scores between 0 and 1 using min-max if needed
            if scores:
                min_s, max_s = float(min(scores)), float(max(scores))
                range_s = max_s - min_s if max_s != min_s else 1.0
                normalized = [(s - min_s) / range_s for s in scores]
            else:
                normalized = [0.0] * len(scores)

            results: list[RerankResult] = []
            for i, sc in enumerate(normalized):
                results.append(RerankResult(index=i, score=float(sc)))

            results.sort(key=lambda x: x.score, reverse=True)
            return results

        # Fallback heuristic (fast, not model-based)
        results = []
        q_tokens = set(query.lower().split())
        for i, doc in enumerate(documents):
            doc_tokens = set(doc.lower().split())
            overlap = len(q_tokens & doc_tokens)
            base = overlap / max(1, len(q_tokens))
            length_penalty = min(1.0, len(doc) / 512)
            score = base * 0.8 + 0.2 * length_penalty
            results.append(RerankResult(index=i, score=float(score)))

        results.sort(key=lambda x: x.score, reverse=True)
        return results
