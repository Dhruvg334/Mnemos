import os
from pydantic import BaseModel, Field

class LLMConfig(BaseModel):
    model_name: str = Field(default="gpt-4-turbo-preview")
    temperature: float = Field(default=0.0)
    api_key: str | None = Field(default=None)
    base_url: str | None = Field(default=None)

class AgenticSettings(BaseModel):
    """
    Settings specific to the AI/Agentic layer.
    """
    primary_llm: LLMConfig = Field(default_factory=LLMConfig)
    fast_llm: LLMConfig = Field(default_factory=lambda: LLMConfig(model_name="gpt-3.5-turbo"))

    # Embedding configuration
    # Supported providers: openai | huggingface | ollama
    embedding_provider: str = Field(default="openai")
    embedding_model: str = "text-embedding-3-small"

    # Cross-Encoder for Reranking
    enable_reranking: bool = True
    cross_encoder_url: str | None = Field(default=None, description="External BGE reranker endpoint")

    # Retrieval thresholds
    min_relevance_score: float = 0.4
    max_retrieval_k: int = 15
    graph_traversal_depth: int = 2

    @classmethod
    def from_env(cls) -> "AgenticSettings":
        return cls(
            primary_llm=LLMConfig(
                model_name=os.getenv("LLM_MODEL", os.getenv("AGENT_MODEL", "gpt-4-turbo-preview")),
                api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY")),
                base_url=os.getenv("LLM_BASE_URL", os.getenv("OPENAI_API_BASE"))
            ),
            fast_llm=LLMConfig(
                model_name=os.getenv("FAST_LLM_MODEL", "gpt-3.5-turbo"),
                api_key=os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY")),
                base_url=os.getenv("LLM_BASE_URL", os.getenv("OPENAI_API_BASE"))
            ),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai").lower(),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            cross_encoder_url=os.getenv("CROSS_ENCODER_URL"),
            enable_reranking=os.getenv("ENABLE_RERANKING", "true").lower() == "true"
        )

agent_settings = AgenticSettings.from_env()
