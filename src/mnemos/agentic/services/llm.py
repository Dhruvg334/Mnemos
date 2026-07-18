from typing import TypeVar, Callable, Any
import time
import hashlib

import httpx
from pydantic import BaseModel

from mnemos.agentic.config import agent_settings
from mnemos.agentic.runtime.model_router import ModelRouter, ModelTier
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("llm_service")
T = TypeVar("T", bound=BaseModel)


class LLMTelemetry:
    """Captures model and retrieval telemetry per call (P0 #18)."""
    def __init__(self) -> None:
        self.records: list[dict] = []
        self._export_sink: Callable[[dict], None] | None = None

    def set_export_sink(self, sink: Callable[[dict], None]) -> None:
        self._export_sink = sink

    def record(self, **kwargs) -> None:  # noqa: ANN003
        entry = {"timestamp": time.time(), **kwargs}
        self.records.append(entry)
        if self._export_sink is not None:
            try:
                self._export_sink(entry)
            except Exception:
                pass

    def summary(self) -> list[dict]:
        return list(self.records)


# Module-level telemetry sink (replaced in tests / observability setup)
_telemetry = LLMTelemetry()


def get_llm_telemetry() -> LLMTelemetry:
    return _telemetry


class LLMService:
    """
    Production-grade LLM client with structured output enforcement,
    model routing (P0 #23), and telemetry recording (P0 #18).
    """
    def __init__(self):
        self.config = agent_settings.primary_llm
        self.api_key = self.config.api_key
        self.base_url = self.config.base_url or "https://api.openai.com/v1"
        self._telemetry = _telemetry

        self._router = ModelRouter(
            fast_model_name=agent_settings.fast_llm.model_name,
            primary_model_name=agent_settings.primary_llm.model_name,
        )

    def _model_for_task(self, task_type: str) -> str:
        """Route to fast or primary model based on task type (P0 #23)."""
        decision = self._router.route(task_type)
        return decision.model_name

    async def call_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_message: str = (
            "You are an industrial intelligence assistant. "
            "Respond with valid JSON matching the schema provided."
        ),
        task_type: str = "reasoning",
    ) -> T:
        """
        Executes a chat completion with JSON mode and parses into a typed Pydantic model.
        Records telemetry (P0 #18).
        """
        model = self._model_for_task(task_type)
        tier = ModelTier.FAST if model == agent_settings.fast_llm.model_name else ModelTier.PRIMARY
        logger.info(f"LLM request: generating {response_model.__name__} model={model} tier={tier.value}")

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=90.0) as client:
            payload = {
                "model": model,
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
                latency_ms = (time.perf_counter() - start) * 1000

                # Record telemetry (P0 #18)
                usage = data.get("usage", {})
                self._telemetry.record(
                    model=model,
                    provider="openai",
                    task_type=task_type,
                    model_tier=tier.value,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    cached_tokens=usage.get("cached_tokens", 0),
                    latency_ms=round(latency_ms, 1),
                    response_model=response_model.__name__,
                )
                self._router.record_latency(tier, latency_ms)

                return response_model.model_validate_json(content)
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM API Error {e.response.status_code}")
                raise
            except Exception as e:
                logger.error(f"Structured LLM execution failed: {type(e).__name__}", exc_info=True)
                raise

    async def get_embeddings(self, text: str) -> list[float]:
        """Returns an embedding vector for `text`. Records telemetry (P0 #18)."""
        provider = (agent_settings.__dict__.get("embedding_provider") or "openai").lower()
        model = agent_settings.embedding_model
        start = time.perf_counter()

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
                    latency_ms = (time.perf_counter() - start) * 1000
                    self._telemetry.record(
                        model=model, provider=provider,
                        task_type="embedding", latency_ms=round(latency_ms, 1),
                        input_length=len(text),
                    )
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
                    ollama_url = agent_settings.primary_llm.base_url or "http://localhost:11434"
                    embed_url = f"{ollama_url.rstrip('/')}/api/embeddings"
                    resp = await client.post(embed_url, json={"model": model, "prompt": text})
                    resp.raise_for_status()
                    return resp.json().get("embedding", [])

                raise ValueError(f"Unsupported embedding provider: {provider}")
            except Exception as e:
                logger.error(f"Embedding generation failed ({provider}): {type(e).__name__}")
                raise

    async def rerank_with_cross_encoder(self, query: str, documents: list[str]) -> list[float]:
        """Rerank documents; records telemetry (P0 #18)."""
        cross_url = agent_settings.__dict__.get("cross_encoder_url")
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                if cross_url:
                    payload = {"query": query, "documents": documents}
                    resp = await client.post(cross_url, json=payload)
                    resp.raise_for_status()
                    scores = resp.json().get("scores", [])
                    latency_ms = (time.perf_counter() - start) * 1000
                    self._telemetry.record(
                        task_type="reranking", latency_ms=round(latency_ms, 1),
                        candidate_count=len(documents),
                        result_count=len(scores),
                    )
                    return scores

                q_emb = await self.get_embeddings(query)
                scores = []
                for d in documents:
                    d_emb = await self.get_embeddings(d)
                    denom = (sum(x*x for x in q_emb) ** 0.5) * (sum(x*x for x in d_emb) ** 0.5)
                    score = 0.0
                    if denom:
                        score = sum(x * y for x, y in zip(q_emb, d_emb, strict=False)) / denom
                    scores.append(float(score))
                return scores
            except Exception as e:
                logger.error(f"Cross-encoder rerank failed: {type(e).__name__}")
                if not documents:
                    return []
                step = 1.0 / max(len(documents), 1)
                return [max(0.0, 1.0 - (i * step)) for i, _ in enumerate(documents)]
