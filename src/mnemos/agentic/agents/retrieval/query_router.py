"""Query Router Agent.

Classifies incoming industrial queries into intents using the LLM.
Determines the primary intent, extracts entity mentions, and infers
time range/site context from the natural-language question.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from mnemos.agentic.agents.retrieval._base import _BaseRetrievalAgent
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import QueryIntent
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("agents.query_router")


class QueryClassification(BaseModel):
    """Structured LLM output for query classification."""

    intent: QueryIntent
    entities: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    time_range: str | None = None
    site_context: str | None = None


class QueryRouterAgent(_BaseRetrievalAgent):
    """Classifies a user query into a typed intent.

    The router uses the LLM to extract:
    - Primary intent (ASSET_INFO, RCA, COMPLIANCE, LESSONS_LEARNED, GENERAL)
    - Entity mentions (asset tags, document references, etc.)
    - Implied time range
    - Site context hint

    Writes to state:
    - ``context["intent"]``
    - ``context["extracted_entities"]``
    - ``context["query_time_range"]``
    - ``context["site_id"]`` (if inferred and not already set)
    """

    name = "query_router"
    role = AgentRole.RETRIEVAL
    description = "Classifies queries into intents using LLM analysis."
    timeout_seconds = 30.0

    def _capabilities(self) -> list[AgentCapability]:
        return [
            AgentCapability(
                name="query_classification",
                description="Produces classified query intent, entities, and context hints.",
                input_types=["raw_query"],
                output_types=["query_intent", "entity_mentions", "query_context"],
            ),
        ]

    @property
    def required_dependencies(self) -> list[str]:
        return []

    async def execute(self, state: AgentState) -> AgentState:
        query = state.get("query", "")
        ctx = dict(state.get("context", {}))

        self.guardrails.detect_injection(query)

        prompt = (
            f"Analyse this industrial query and extract:\n"
            f"- intent: one of asset_info, rca, compliance, lessons_learned, general\n"
            f"- entities: list of asset tags, document names, or identifiers mentioned\n"
            f"- confidence: float 0.0-1.0\n"
            f"- time_range: any implied time range (e.g. 'last 3 months', '2024')\n"
            f"- site_context: any site code or name mentioned\n\n"
            f"Query: '{query}'"
        )

        classification: QueryClassification = await self.llm.call_structured(
            prompt, QueryClassification
        )

        ctx["intent"] = classification.intent
        ctx["extracted_entities"] = classification.entities
        ctx["query_time_range"] = classification.time_range

        if classification.site_context and not ctx.get("site_id"):
            ctx["site_id"] = classification.site_context

        state["context"] = ctx

        logger.info(
            f"Query classified: intent={classification.intent}, "
            f"entities={classification.entities}, confidence={classification.confidence}"
        )

        return state
