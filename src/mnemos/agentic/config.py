from typing import Optional
from pydantic import BaseModel, Field
from mnemos.core.config import settings

class LLMConfig(BaseModel):
    model_name: str = Field(default="gpt-4-turbo-preview")
    temperature: float = Field(default=0.0)
    max_tokens: Optional[int] = Field(default=None)
    api_key: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)

class AgenticSettings(BaseModel):
    """
    Settings specific to the AI/Agentic layer.
    Can be initialized from the main app settings.
    """
    primary_llm: LLMConfig = Field(default_factory=LLMConfig)
    fast_llm: LLMConfig = Field(default_factory=lambda: LLMConfig(model_name="gpt-3.5-turbo"))

    embedding_model: str = "text-embedding-3-small"

    # Retrieval thresholds
    min_confidence_score: float = 0.7
    max_retrieval_k: int = 10

    # Graph settings
    graph_traversal_depth: int = 2

    # Feature flags
    enable_reranking: bool = True
    enable_graph_context: bool = True

    @classmethod
    def from_env(cls) -> "AgenticSettings":
        # In a real app, this would pull from env vars or the main settings object
        return cls()

agent_settings = AgenticSettings.from_env()
