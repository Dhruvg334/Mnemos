from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.langgraph.nodes import (
    EvidenceRetrievalNode,
    QueryRouterNode,
    ResponseComposerNode,
)
from mnemos.agentic.schemas.base import AgentResponse, QueryIntent, RetrievalPlan, RetrievalStrategy
from mnemos.agentic.schemas.state import AgentState


class BaselineVectorRetrievalNode(EvidenceRetrievalNode):
    """
    Overrides the standard retrieval node to strictly use vector search only.
    Bypasses Knowledge Graph traversal and Metadata filtering.
    """
    async def execute(self, state: AgentState) -> AgentState:
        # Force the plan to vector-only
        state["retrieval_plan"] = RetrievalPlan(
            intent=QueryIntent.GENERAL,
            strategies=[RetrievalStrategy.VECTOR_SEARCH],
            target_entities=[],
            reasoning="Evaluation Baseline: Vector-only retrieval."
        )
        # Execute standard retrieval which will now only run the vector task
        return await super().execute(state)

class BaselineVectorRAGOrchestrator:
    """
    A baseline pipeline implementing standard 'Document -> Chunk -> Answer' RAG.
    Used to measure the performance improvement of the Mnemos Asset-Centric approach.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.workflow = self._build_baseline_workflow()

    def _build_baseline_workflow(self):
        workflow = StateGraph(AgentState)

        # We reuse the standard router and composer, but use the restricted retrieval node
        router = QueryRouterNode(self.db)
        retrieval = BaselineVectorRetrievalNode(self.db)
        composer = ResponseComposerNode(self.db)

        workflow.add_node("router", router)
        workflow.add_node("retrieval", retrieval)
        workflow.add_node("composer", composer)

        workflow.set_entry_point("router")
        workflow.add_edge("router", "retrieval")
        workflow.add_edge("retrieval", "composer")
        workflow.add_edge("composer", END)

        return workflow.compile()

    async def run_baseline(self, question: str, context_metadata: dict[str, Any]) -> AgentResponse:
        """
        Executes a query through the baseline vector-only pipeline.
        """
        initial_state: AgentState = {
            "query": question,
            "context": context_metadata,
            "intent": None,
            "resolved_entities": [],
            "retrieval_plan": None,
            "evidence_bundle": None,
            "messages": [],
            "claims": [],
            "final_response": None,
            "steps_completed": [],
            "errors": []
        }

        final_state = await self.workflow.ainvoke(initial_state)
        return final_state["final_response"]
