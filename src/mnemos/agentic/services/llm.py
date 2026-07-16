from typing import TypeVar

import httpx
from pydantic import BaseModel

from mnemos.agentic.config import agent_settings
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("llm_service")
T = TypeVar("T", bound=BaseModel)

class LLMService:
    """
    Production-grade LLM client with structured output enforcement and site-aware security.
    """
    def __init__(self):
        self.config = agent_settings.primary_llm
        self.api_key = self.config.api_key
        self.base_url = self.config.base_url or "https://api.openai.com/v1"

    async def call_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_message: str = (
            "You are an industrial intelligence assistant. "
            "Respond with valid JSON matching the schema provided."
        ),
    ) -> T:
        """
        Executes a chat completion with JSON mode and parses into a typed Pydantic model.
        """
        logger.info(f"LLM request: generating {response_model.__name__}")

        async with httpx.AsyncClient(timeout=90.0) as client:
            payload = {
                "model": self.config.model_name,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": self.config.temperature
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                return response_model.model_validate_json(content)
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM API Error {e.response.status_code}: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Structured LLM execution failed: {str(e)}", exc_info=True)
                raise

    async def get_embeddings(self, text: str) -> list[float]:
        """
        Returns an embedding vector for `text` using configured provider.
        Supported providers: openai, huggingface, ollama
        """
        provider = (agent_settings.__dict__.get("embedding_provider") or "openai").lower()
        model = agent_settings.embedding_model

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                if provider == "openai":
                    base = agent_settings.primary_llm.base_url or self.base_url
                    url = base.rstrip("/") + "/embeddings"
                    payload = {"model": model, "input": text}
                    headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return data.get("data", [])[0].get("embedding", [])

                if provider == "huggingface":
                    hf_key = agent_settings.primary_llm.api_key
                    url = "https://api-inference.huggingface.co/embeddings"
                    payload = {"inputs": text, "model": model}
                    headers = {"Authorization": f"Bearer {hf_key}"} if hf_key else {}
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    return resp.json().get("embedding") or resp.json()

                if provider == "ollama":
                    # Default Ollama local API
                    ollama_url = agent_settings.primary_llm.base_url or "http://localhost:11434"
                    embed_url = f"{ollama_url.rstrip('/')}/api/embeddings"
                    resp = await client.post(embed_url, json={"model": model, "prompt": text})
                    resp.raise_for_status()
                    return resp.json().get("embedding", [])

                raise ValueError(
                    f"Unsupported embedding provider: {provider}"
                )
            except Exception as e:
                logger.error(f"Embedding generation failed ({provider}): {e}")
                raise

    async def rerank_with_cross_encoder(self, query: str, documents: list[str]) -> list[float]:
        """
        Attempts to rerank documents using a dedicated cross-encoder endpoint if configured.
        Fallbacks to embedding-based similarity if no endpoint is configured.
        Returns list of scores aligned with `documents`.
        """
        cross_url = agent_settings.__dict__.get("cross_encoder_url")
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                if cross_url:
                    payload = {"query": query, "documents": documents}
                    resp = await client.post(cross_url, json=payload)
                    resp.raise_for_status()
                    return resp.json().get("scores", [])

                # Fallback: use embedding cosine similarity
                q_emb = await self.get_embeddings(query)
                scores = []
                for d in documents:
                    d_emb = await self.get_embeddings(d)
                    # cosine similarity
                    denom = (sum(x*x for x in q_emb) ** 0.5) * (sum(x*x for x in d_emb) ** 0.5)
                    score = 0.0
                    if denom:
                        score = sum(x * y for x, y in zip(q_emb, d_emb, strict=False)) / denom
                    scores.append(float(score))
                return scores
            except Exception as e:
                logger.error(f"Cross-encoder rerank failed: {e}")
                # Degraded mode: preserve the original candidate ordering
                # instead of deleting all evidence with zero scores.
                if not documents:
                    return []
                step = 1.0 / max(len(documents), 1)
                return [
                    max(0.0, 1.0 - (index * step))
                    for index, _ in enumerate(documents)
                ]
