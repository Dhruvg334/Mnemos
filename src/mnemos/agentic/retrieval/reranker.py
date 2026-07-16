from pydantic import BaseModel

from mnemos.agentic.deps import get_llm_service


class RerankResult(BaseModel):
    index: int
    score: float

class BaseReranker:
    """
    Abstract base class for reranking evidence.
    """
    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        raise NotImplementedError

class CrossEncoderReranker(BaseReranker):
    """
    Implements reranking using a Cross-Encoder model (e.g., BGE-Reranker).
    Cross-encoders are more accurate than bi-encoders for relevance scoring
    as they process the query and document simultaneously.
    """
    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        # Prefer using configured cross-encoder endpoint via LLMService
        self.llm = get_llm_service()

    async def rerank(self, query: str, documents: list[str]) -> list[RerankResult]:
        """
        Scores each document against the query.
        Returns a list of RerankResult sorted by score.
        """
        if not documents:
            return []

        # Try dedicated cross-encoder endpoint first
        scores = await self.llm.rerank_with_cross_encoder(query, documents)

        # Normalize length
        if len(scores) != len(documents):
            # Fallback: uniform scores
            src = scores or [0.0] * len(documents)
            scores = []
            for s in src:
                scores.append(float(s) if isinstance(s, int | float) else 0.0)

        results = []
        for i in range(len(documents)):
            results.append(RerankResult(index=i, score=float(scores[i] if i < len(scores) else 0.0)))
        results.sort(key=lambda x: x.score, reverse=True)
        return results
