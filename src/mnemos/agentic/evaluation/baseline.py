from typing import Any, Dict, List, Optional
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.schemas.base import (
    QueryIntent,
    RetrievalPlan,
    RetrievalStrategy,
    AgentResponse,
    AgentMessage,
    MessageRole
)
from mnemos.agentic.langgraph.nodes import BaseNode, QueryRouterNode, EvidenceRetrievalNode, ResponseComposerNode

class BaselineVectorRetrievalNode(EvidenceRetrievalNode):
    """
    Overrides the retrieval node to force a vector-only strategy.
    """
    async def execute(self, state: AgentState) -> AgentState:
        # Force plan to only use vector search
        state["retrieval_plan"] = RetrievalPlan(
            intent=QueryIntent.GENERAL,
            strategies=[RetrievalStrategy.VECTOR_SEARCH],
            target_entities=[],
            reasoning="Baseline: Vector-only retrieval."
        )
        # Call the parent retrieval logic which will now only use the vector search strategy
        return await super().execute(state)

class BaselineVectorRAGOrchestrator:
    """
    A baseline pipeline that implements standard Vector-only RAG.
    Used as a control group for comparative evaluation.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow = self._build_baseline_workflow()

    def _build_baseline_workflow(self):
        workflow = StateGraph(AgentState)

        router = QueryRouterNode()
        retrieval = BaselineVectorRetrievalNode()
        composer = ResponseComposerNode()

        workflow.add_node("router", router)
        workflow.add_node("retrieval", retrieval)
        workflow.add_node("composer", composer)

        workflow.set_entry_point("router")
        workflow.add_edge("router", "retrieval")
        workflow.add_edge("retrieval", "composer")
        workflow.add_edge("composer", END)

        return workflow.compile()

    async def run(self, query_id: str, question: str, context: Dict[str, Any]) -> AgentResponse:
        initial_state: AgentState = {
            "query": question,
            "context": {**context, "query_id": query_id},
            "intent": None,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "current_node": "START",
            "errors": []
        }

        final_state = await self.workflow.ainvoke(initial_state)
        return final_state["final_response"]
