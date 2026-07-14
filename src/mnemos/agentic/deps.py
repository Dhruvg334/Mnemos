import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.config import AgenticSettings, agent_settings
from mnemos.agentic.prompts.manager import PromptManager
from mnemos.agentic.retrieval.interfaces import BaseRetriever
from mnemos.agentic.graph.interfaces import BaseGraphClient
from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.retrieval.engine import HybridRetrievalEngine
from mnemos.agentic.services.llm import LLMService
from mnemos.agentic.services.resource_pool import ResourcePool
from mnemos.core.db import get_db
from mnemos.core.config import settings


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
    """
    Returns the production Neo4j graph client using shared resource pool.
    """
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    # In production, we'd use ResourcePool.get_neo4j_driver() here
    return Neo4jGraphClient(uri=uri, user=user, password=password)


async def get_retriever(
    db: AsyncSession = Depends(get_db),
    graph_client: BaseGraphClient = Depends(get_graph_client)
) -> BaseRetriever:
    """
    Returns the production Hybrid Retrieval Engine.
    """
    return HybridRetrievalEngine(db=db, graph_client=graph_client)


AgentSettingsDep = Annotated[AgenticSettings, Depends(get_agent_settings)]
PromptManagerDep = Annotated[PromptManager, Depends(get_prompt_manager)]
RetrieverDep = Annotated[BaseRetriever, Depends(get_retriever)]
GraphClientDep = Annotated[BaseGraphClient, Depends(get_graph_client)]
LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]
