"""Retrieval Planner Agent.

Uses the LLM to dynamically select retrieval strategies, compute
asset scope, date/revision/permission filters, and evidence
sufficiency thresholds.  Falls back to intent-based defaults
when the LLM is unavailable or returns an invalid plan.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mnemos.agentic.agents.retrieval._base import _BaseRetrievalAgent
from mnemos.agentic.config import agent_settings
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import (
    QueryIntent,
    RetrievalPlan,
    RetrievalStrategy,
)
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("agents.retrieval_planner")

# ------------------------------------------------------------------
# LLM output model
# ------------------------------------------------------------------


class PlannerLLMOutput(BaseModel):
    """Structured output the LLM produces for plan generation."""

    strategies: list[RetrievalStrategy] = Field(
        description="Ordered list of retrieval strategies to execute.",
    )
    asset_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    latest_version_only: bool = True
    document_versions: list[int] | None = None
    top_k_per_strategy: int = 10
    min_relevance_score: float = 0.4
    min_evidence_count: int = 3
    min_average_confidence: float = 0.6
    reasoning: str = ""


# ------------------------------------------------------------------
# Intent-based defaults (used when LLM is unavailable)
# ------------------------------------------------------------------

_INTENT_DEFAULTS: dict[QueryIntent, dict[str, Any]] = {
    QueryIntent.ASSET_INFO: {
        "strategies": [
            RetrievalStrategy.METADATA_FILTER,
            RetrievalStrategy.GRAPH_TRAVERSAL,
            RetrievalStrategy.VECTOR_SEARCH,
            RetrievalStrategy.LEXICAL_SEARCH,
            RetrievalStrategy.RERANKING,
        ],
        "min_evidence_count": 3,
        "latest_version_only": True,
    },
    QueryIntent.RCA: {
        "strategies": [
            RetrievalStrategy.SQL_QUERY,
            RetrievalStrategy.GRAPH_TRAVERSAL,
            RetrievalStrategy.VECTOR_SEARCH,
            RetrievalStrategy.LEXICAL_SEARCH,
            RetrievalStrategy.RERANKING,
        ],
        "min_evidence_count": 5,
        "latest_version_only": False,
    },
    QueryIntent.COMPLIANCE: {
        "strategies": [
            RetrievalStrategy.METADATA_FILTER,
            RetrievalStrategy.SQL_QUERY,
            RetrievalStrategy.LEXICAL_SEARCH,
            RetrievalStrategy.VECTOR_SEARCH,
            RetrievalStrategy.RERANKING,
        ],
        "min_evidence_count": 4,
        "latest_version_only": True,
    },
    QueryIntent.LESSONS_LEARNED: {
        "strategies": [
            RetrievalStrategy.VECTOR_SEARCH,
            RetrievalStrategy.LEXICAL_SEARCH,
            RetrievalStrategy.GRAPH_TRAVERSAL,
            RetrievalStrategy.RERANKING,
        ],
        "min_evidence_count": 3,
        "latest_version_only": False,
    },
    QueryIntent.GENERAL: {
        "strategies": [
            RetrievalStrategy.VECTOR_SEARCH,
            RetrievalStrategy.LEXICAL_SEARCH,
            RetrievalStrategy.GRAPH_TRAVERSAL,
            RetrievalStrategy.RERANKING,
        ],
        "min_evidence_count": 3,
        "latest_version_only": True,
    },
}


class RetrievalPlannerAgent(_BaseRetrievalAgent):
    """Creates a retrieval plan from the classified intent.

    The planner uses the LLM to reason about:
    - Which retrieval strategies are needed for this specific query
    - Asset scope (which assets to restrict search to)
    - Date filters (recency requirements)
    - Revision filters (current-only vs. historical)
    - Permission/tenancy filters
    - Evidence sufficiency thresholds

    Falls back to intent-based defaults if the LLM call fails.

    Reads from state:
    - ``context["intent"]`` (set by QueryRouterAgent)
    - ``context["extracted_entities"]`` (entity mentions)
    - ``context["resolved_entities"]`` (resolved entity IDs)
    - ``context["query_time_range"]`` (time hint)
    - ``context["site_id"]``, ``context["org_id"]``

    Writes to state:
    - ``context["retrieval_plan"]`` (a ``RetrievalPlan``)
    """

    name = "retrieval_planner"
    role = AgentRole.RETRIEVAL
    description = (
        "LLM-driven planner that selects retrieval strategies and "
        "computes asset, date, revision, and permission filters."
    )
    timeout_seconds = 30.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="retrieval_planning",
                description="Produces a fully-specified retrieval plan with strategies and filters.",
                input_types=["query_intent", "entity_mentions", "query_context"],
                output_types=["retrieval_plan"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return ["query_router"]

    async def execute(self, state: AgentState) -> AgentState:
        ctx = dict(state.get("context", {}))
        intent = ctx.get("intent", QueryIntent.GENERAL)

        if isinstance(intent, str):
            try:
                intent = QueryIntent(intent)
            except ValueError:
                intent = QueryIntent.GENERAL

        # Build context summary for LLM
        context_summary = self._build_context_summary(ctx, state.get("query", ""))

        try:
            llm_output: PlannerLLMOutput = await self.llm.call_structured(
                self._build_planner_prompt(context_summary),
                PlannerLLMOutput,
            )
            plan = self._plan_from_llm(ctx, intent, llm_output)
            logger.info(
                f"LLM plan created: intent={intent.value}, "
                f"strategies={[s.value for s in plan.strategies]}, "
                f"reasoning={plan.reasoning[:100]}"
            )
        except Exception as exc:
            logger.warning(f"LLM planner failed ({exc}), using intent defaults")
            plan = self._plan_from_defaults(ctx, intent)

        ctx["retrieval_plan"] = plan
        state["context"] = ctx
        return state

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_context_summary(self, ctx: dict[str, Any], query: str) -> str:
        parts = [f"Query: {query}"]

        intent = ctx.get("intent", "unknown")
        parts.append(f"Classified intent: {intent}")

        extracted = ctx.get("extracted_entities", [])
        if extracted:
            parts.append(f"Extracted entity mentions: {extracted}")

        resolved = ctx.get("resolved_entities", [])
        if resolved:
            entity_ids = [
                e.get("entity_id", "") if isinstance(e, dict) else getattr(e, "entity_id", "")
                for e in resolved
            ]
            parts.append(f"Resolved entity IDs: {entity_ids}")

        time_range = ctx.get("query_time_range")
        if time_range:
            parts.append(f"Implied time range: {time_range}")

        site_id = ctx.get("site_id")
        org_id = ctx.get("org_id")
        parts.append(f"Site: {site_id or 'any'}, Org: {org_id or 'any'}")

        return "\n".join(parts)

    def _build_planner_prompt(self, context_summary: str) -> str:
        available_strategies = ", ".join(s.value for s in RetrievalStrategy)
        return (
            "You are an industrial retrieval planner. Given the query context below, "
            "produce a retrieval plan.\n\n"
            f"Available strategies: {available_strategies}\n\n"
            "Decide:\n"
            "1. Which strategies to use and in what order (primary strategies first)\n"
            "2. Asset scope -- which asset_ids to restrict to (empty = no restriction)\n"
            "3. Document scope -- specific document_ids if relevant\n"
            "4. Date filters -- date_from/date_to in ISO-8601 if the query implies recency\n"
            "5. Revision filters -- latest_version_only=true for current docs, false for RCA/audit\n"
            "6. top_k_per_strategy -- how many candidates per strategy (5-15)\n"
            "7. min_relevance_score -- threshold after reranking (0.3-0.7)\n"
            "8. min_evidence_count -- minimum verified items needed (2-8)\n"
            "9. min_average_confidence -- minimum avg confidence to consider sufficient (0.5-0.8)\n\n"
            f"Context:\n{context_summary}\n\n"
            "Return a JSON object matching the PlannerLLMOutput schema."
        )

    # ------------------------------------------------------------------
    # Plan construction
    # ------------------------------------------------------------------

    def _plan_from_llm(
        self,
        ctx: dict[str, Any],
        intent: QueryIntent,
        llm_out: PlannerLLMOutput,
    ) -> RetrievalPlan:
        # Ensure at least one strategy
        strategies = llm_out.strategies or _INTENT_DEFAULTS.get(
            intent, _INTENT_DEFAULTS[QueryIntent.GENERAL]
        )["strategies"]

        # Merge entity IDs from resolved entities if LLM didn't specify
        asset_ids = llm_out.asset_ids or [
            e.get("entity_id", "") if isinstance(e, dict) else getattr(e, "entity_id", "")
            for e in ctx.get("resolved_entities", [])
        ]

        return RetrievalPlan(
            intent=intent,
            strategies=strategies,
            target_entities=asset_ids,
            asset_ids=asset_ids,
            document_ids=llm_out.document_ids,
            date_from=llm_out.date_from,
            date_to=llm_out.date_to,
            latest_version_only=llm_out.latest_version_only,
            document_versions=llm_out.document_versions,
            filters={
                "site_id": ctx.get("site_id"),
                "org_id": ctx.get("org_id"),
            },
            site_id=ctx.get("site_id"),
            organisation_id=ctx.get("org_id"),
            top_k_per_strategy=llm_out.top_k_per_strategy,
            min_relevance_score=llm_out.min_relevance_score,
            min_evidence_count=llm_out.min_evidence_count,
            min_average_confidence=llm_out.min_average_confidence,
            enable_reranking=agent_settings.enable_reranking,
            reasoning=llm_out.reasoning or f"LLM plan for intent={intent.value}",
        )

    def _plan_from_defaults(
        self,
        ctx: dict[str, Any],
        intent: QueryIntent,
    ) -> RetrievalPlan:
        defaults = _INTENT_DEFAULTS.get(intent, _INTENT_DEFAULTS[QueryIntent.GENERAL])

        asset_ids = [
            e.get("entity_id", "") if isinstance(e, dict) else getattr(e, "entity_id", "")
            for e in ctx.get("resolved_entities", [])
        ]

        # Infer date range from query_time_range hint
        time_range = ctx.get("query_time_range")

        return RetrievalPlan(
            intent=intent,
            strategies=defaults["strategies"],
            target_entities=asset_ids,
            asset_ids=asset_ids,
            date_from=None,
            date_to=None,
            latest_version_only=defaults["latest_version_only"],
            filters={
                "site_id": ctx.get("site_id"),
                "org_id": ctx.get("org_id"),
            },
            site_id=ctx.get("site_id"),
            organisation_id=ctx.get("org_id"),
            top_k_per_strategy=agent_settings.max_retrieval_k,
            min_relevance_score=agent_settings.min_relevance_score,
            min_evidence_count=defaults["min_evidence_count"],
            min_average_confidence=0.6,
            enable_reranking=agent_settings.enable_reranking,
            reasoning=f"Intent-based defaults for {intent.value}"
            + (f" with time_range={time_range}" if time_range else ""),
        )
