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
from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    MCPToolName,
    RetrievalPlan,
    RetrievalStrategy,
)
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
        ctx = state.get("context")
        if not isinstance(ctx, dict):
            ctx = {}
            state["context"] = ctx
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

        # Apply agent-level permission filtering
        bundle = self._filter_by_permissions(bundle, ctx)

        # Enrich the hybrid retrieval result with governed tool calls. The
        # tool budget is bounded in the shared base class, and only assets
        # already permitted by the retrieval plan are used.
        if self._mcp_server is not None:
            asset_ids = list(dict.fromkeys(plan.asset_ids))[:2]
            if RetrievalStrategy.GRAPH_TRAVERSAL in plan.strategies:
                for asset_id in asset_ids:
                    graph_result = await self.call_tool(
                        MCPToolName.GRAPH_TRAVERSAL,
                        {
                            "start_node_id": asset_id,
                            "graph_type": "failure_graph",
                            "depth": min(plan.max_hops, 3),
                            "limit": min(plan.top_k_per_strategy * 5, 50),
                        },
                        state=state,
                    )
                    if isinstance(graph_result, dict) and not graph_result.get("error"):
                        bundle.raw_graph_data.setdefault(asset_id, graph_result)

            if plan.intent.value in {"asset_info", "rca", "lessons_learned"}:
                timelines = bundle.metadata.setdefault("tool_timelines", {})
                for asset_id in asset_ids:
                    timeline_result = await self.call_tool(
                        MCPToolName.TIMELINE,
                        {
                            "asset_id": asset_id,
                            "date_from": plan.date_from,
                            "date_to": plan.date_to,
                            "limit": min(plan.top_k_per_strategy * 10, 100),
                        },
                        state=state,
                    )
                    if isinstance(timeline_result, dict) and not timeline_result.get("error"):
                        timelines[asset_id] = timeline_result

        ctx["evidence_bundle"] = bundle
        state["context"] = ctx

        # Populate the shared evidence list for downstream agents
        evidence_list: list[dict[str, Any]] = list(state.get("evidence", []))
        for vec in bundle.raw_vector_data:
            evidence_list.append(
                {
                    "source": "vector",
                    "content": vec.get("content", ""),
                    "metadata": vec.get("metadata", {}),
                    "score": vec.get("rerank_score", vec.get("score", 0.0)),
                }
            )
        for entity_id, data in bundle.raw_graph_data.items():
            evidence_list.append(
                {
                    "source": "graph",
                    "entity_id": entity_id,
                    "nodes_count": len(data.get("nodes", [])),
                    "relationships_count": len(data.get("relationships", [])),
                }
            )

        state["evidence"] = evidence_list

        logger.info(
            f"Retrieval complete: {len(bundle.raw_vector_data)} candidates, "
            f"{len(bundle.raw_graph_data)} graph traversals, "
            f"{len(bundle.resolved_entities)} entities resolved"
        )

        return state

    def _filter_by_permissions(
        self,
        bundle: EvidenceBundle,
        ctx: dict[str, Any],
    ) -> EvidenceBundle:
        """Filter evidence to only include sources within user's permitted scope.

        Checks site_id and org_id from the user context against each
        evidence source's provenance. Removes any evidence that falls
        outside the user's authorized scope.
        """
        user_site = ctx.get("site_id")
        user_org = ctx.get("org_id")

        if not user_site and not user_org:
            return bundle

        original_count = len(bundle.verified_evidence)
        filtered_evidence = []

        for source in bundle.verified_evidence:
            # Check site scope
            if user_site:
                source_site = source.metadata.get("site_id", "")
                if source_site and source_site != user_site:
                    continue

            # Check org scope
            if user_org:
                source_org = source.metadata.get("org_id", "")
                if source_org and source_org != user_org:
                    continue

            filtered_evidence.append(source)

        if len(filtered_evidence) < original_count:
            logger.info(
                f"Permission filter: {original_count} -> {len(filtered_evidence)} "
                f"evidence sources (site={user_site}, org={user_org})"
            )

        bundle.verified_evidence = filtered_evidence
        return bundle
