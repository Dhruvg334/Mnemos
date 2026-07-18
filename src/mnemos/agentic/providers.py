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


async def get_graph_client() -> BaseGraphClient:
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("NEO4J_PASSWORD environment variable is required")
    return Neo4jGraphClient(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=password,
    )
