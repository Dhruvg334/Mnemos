"""Evidence Retrieval Agent.

Executes the retrieval plan produced by the RetrievalPlanner agent
using the HybridRetrievalEngine.  Passes the full plan (including
asset scope, date, revision, and permission filters) to the engine
so that filters are applied at the source.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.agents.retrieval._base import _BaseRetrievalAgent
from mnemos.agentic.deps import get_graph_client
from mnemos.agentic.retrieval.engine import HybridRetrievalEngine
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import EvidenceBundle, RetrievalPlan
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("agents.evidence_retrieval")


class EvidenceRetrievalAgent(_BaseRetrievalAgent):
    """Executes the retrieval plan and gathers raw evidence.

    Reads from state:
    - ``context["retrieval_plan"]`` (a ``RetrievalPlan``)
    - ``context["query_id"]``, ``context["site_id"]``

    Writes to state:
    - ``context["evidence_bundle"]`` (an ``EvidenceBundle``)
    - ``evidence`` list (individual evidence dicts for downstream agents)
    """

    name = "evidence_retrieval"
    role = AgentRole.RETRIEVAL
    description = "Executes retrieval plan via HybridRetrievalEngine."
    timeout_seconds = 120.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="evidence_gathering",
                description="Executes multi-modal retrieval and produces an evidence bundle.",
                input_types=["retrieval_plan", "query_context"],
                output_types=["evidence_bundle", "evidence_list"],
                dependencies=["retrieval_planning"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return ["retrieval_planner"]

    async def execute(self, state: AgentState) -> AgentState:
        ctx = dict(state.get("context", {}))
        plan: RetrievalPlan | None = ctx.get("retrieval_plan")

        if plan is None:
            logger.warning("No retrieval plan found; skipping evidence retrieval.")
            return state

        graph_client = await get_graph_client()
        engine = HybridRetrievalEngine(self.db, graph_client)

        query_id = ctx.get("query_id", "unknown")
        query_text = state.get("query", "")

        logger.info(
            f"Executing retrieval plan for query_id={query_id} "
            f"strategies={[s.value for s in plan.strategies]}"
        )

        bundle: EvidenceBundle = await engine.execute_plan(
            query_id=query_id,
            query_text=query_text,
            plan=plan,
            context=ctx,
        )

        ctx["evidence_bundle"] = bundle
        state["context"] = ctx

        # Populate the shared evidence list for downstream agents
        evidence_list: list[dict[str, Any]] = list(state.get("evidence", []))
        for vec in bundle.raw_vector_data:
            evidence_list.append({
                "source": "vector",
                "content": vec.get("content", ""),
                "metadata": vec.get("metadata", {}),
                "score": vec.get("rerank_score", vec.get("score", 0.0)),
            })
        for entity_id, data in bundle.raw_graph_data.items():
            evidence_list.append({
                "source": "graph",
                "entity_id": entity_id,
                "nodes_count": len(data.get("nodes", [])),
                "relationships_count": len(data.get("relationships", [])),
            })

        state["evidence"] = evidence_list

        logger.info(
            f"Retrieval complete: {len(bundle.raw_vector_data)} candidates, "
            f"{len(bundle.raw_graph_data)} graph traversals, "
            f"{len(bundle.resolved_entities)} entities resolved"
        )

        return state
