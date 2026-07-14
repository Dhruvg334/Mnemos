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
        system_message: str = "You are an industrial intelligence assistant. You MUST respond with valid JSON matching the schema provided."
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
