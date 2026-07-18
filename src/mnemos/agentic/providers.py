import os
from functools import lru_cache

from mnemos.agentic.config import AgenticSettings, agent_settings
from mnemos.agentic.graph.interfaces import BaseGraphClient
from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.prompts.manager import PromptManager
from mnemos.agentic.services.llm import LLMService


@lru_cache
def get_agent_settings() -> AgenticSettings:
    return agent_settings


@lru_cache
def get_prompt_manager() -> PromptManager:
    return PromptManager()


@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()


_graph_client_cache: BaseGraphClient | None = None
_graph_client_lock: bool = False


async def get_graph_client() -> BaseGraphClient:
    """Get the singleton Neo4j graph client (async-safe cached)."""
    global _graph_client_cache, _graph_client_lock  # noqa: PLW0603

    if _graph_client_cache is not None:
        return _graph_client_cache

    if _graph_client_lock:
        from mnemos.agentic.utils.exceptions import ConfigurationError
        raise ConfigurationError("Graph client creation already in progress")

    _graph_client_lock = True
    try:
        password = os.environ.get("NEO4J_PASSWORD")
        if not password:
            raise RuntimeError("NEO4J_PASSWORD environment variable is required")
        _graph_client_cache = Neo4jGraphClient(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=password,
        )
        return _graph_client_cache
    finally:
        _graph_client_lock = False
