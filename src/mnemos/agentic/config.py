import os

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    model_name: str = Field(default="llama3-70b-8192")
    temperature: float = Field(default=0.0)
    api_key: str | None = Field(default=None)
    base_url: str | None = Field(default="https://api.groq.com/openai/v1")


class AgenticSettings(BaseModel):
    """
    Settings specific to the AI/Agentic layer.
    """

    primary_llm: LLMConfig = Field(default_factory=LLMConfig)
    fast_llm: LLMConfig = Field(
        default_factory=lambda: LLMConfig(
            model_name="llama3-8b-8192", base_url="https://api.groq.com/openai/v1"
        )
    )

    # Embedding configuration
    # Supported providers: openai | huggingface | ollama
    # Note: Groq currently does not provide an embedding API.
    embedding_provider: str = Field(default="openai")
    embedding_model: str = "text-embedding-3-small"

    # Cross-Encoder for Reranking
    enable_reranking: bool = True
    cross_encoder_url: str | None = Field(
        default=None, description="External BGE reranker endpoint"
    )

    # Retrieval thresholds
    min_relevance_score: float = 0.4
    max_retrieval_k: int = 15
    graph_traversal_depth: int = 2

    # Budget
    max_total_candidates: int = 100
    budget_tokens: int | None = None
    max_multi_hop: int = 3
    max_retrieval_retries: int = 3

    @classmethod
    def from_env(cls) -> "AgenticSettings":
        groq_base = "https://api.groq.com/openai/v1"
        return cls(
            primary_llm=LLMConfig(
                model_name=os.getenv("LLM_MODEL", os.getenv("GROQ_MODEL", "llama3-70b-8192")),
                api_key=os.getenv("GROQ_API_KEY", os.getenv("LLM_API_KEY")),
                base_url=os.getenv("GROQ_API_BASE", os.getenv("LLM_BASE_URL", groq_base)),
            ),
            fast_llm=LLMConfig(
                model_name=os.getenv("FAST_LLM_MODEL", "llama3-8b-8192"),
                api_key=os.getenv("GROQ_API_KEY", os.getenv("LLM_API_KEY")),
                base_url=os.getenv("GROQ_API_BASE", os.getenv("LLM_BASE_URL", groq_base)),
            ),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "openai").lower(),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            cross_encoder_url=os.getenv("CROSS_ENCODER_URL"),
            enable_reranking=os.getenv("ENABLE_RERANKING", "true").lower() == "true",
        )


agent_settings = AgenticSettings.from_env()
