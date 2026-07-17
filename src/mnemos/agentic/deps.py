from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.config import AgenticSettings
from mnemos.agentic.graph.interfaces import BaseGraphClient
from mnemos.agentic.prompts.manager import PromptManager
from mnemos.agentic.providers import (
    get_agent_settings,
    get_graph_client,
    get_llm_service,
    get_prompt_manager,
)
from mnemos.agentic.retrieval.engine import HybridRetrievalEngine
from mnemos.agentic.retrieval.interfaces import BaseRetriever
from mnemos.agentic.services.llm import LLMService
from mnemos.core.db import get_db


async def get_retriever(
    db: AsyncSession = Depends(get_db),
    graph_client: BaseGraphClient = Depends(get_graph_client),
) -> BaseRetriever:
    return HybridRetrievalEngine(db=db, graph_client=graph_client)


AgentSettingsDep = Annotated[AgenticSettings, Depends(get_agent_settings)]
PromptManagerDep = Annotated[PromptManager, Depends(get_prompt_manager)]
RetrieverDep = Annotated[BaseRetriever, Depends(get_retriever)]
GraphClientDep = Annotated[BaseGraphClient, Depends(get_graph_client)]
LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]
