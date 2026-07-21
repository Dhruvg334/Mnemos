"""Query Router Agent.

Classifies incoming industrial queries into intents using the LLM.
Determines the primary intent, extracts entity mentions, and infers
time range/site context from the natural-language question.

When entity resolution is ambiguous the router requests clarification
rather than proceeding with a guess.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from mnemos.agentic.agents.retrieval._base import _BaseRetrievalAgent
from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import MCPToolName, QueryIntent, ResolvedEntity
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
    clarification_needed: bool = Field(
        default=False,
        description="True when entities are ambiguous and user clarification is required.",
    )
    clarification_questions: list[str] = Field(
        default_factory=list,
        description="Specific questions to ask the user to resolve ambiguity.",
    )


class QueryRouterAgent(_BaseRetrievalAgent):
    """Classifies a user query into a typed intent.

    The router uses the LLM to extract:
    - Primary intent (ASSET_INFO, RCA, COMPLIANCE, LESSONS_LEARNED, GENERAL)
    - Entity mentions (asset tags, document references, etc.)
    - Implied time range
    - Site context hint

    When entity resolution is ambiguous the router sets
    ``context["clarification_required"] = True`` and populates
    ``context["clarification_questions"]`` so the supervisor can
    pause and request user input before proceeding.

    Writes to state:
    - ``context["intent"]``
    - ``context["extracted_entities"]``
    - ``context["query_time_range"]``
    - ``context["site_id"]`` (if inferred and not already set)
    - ``context["clarification_required"]`` (bool)
    - ``context["clarification_questions"]`` (list[str])
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
        ctx = state.get("context")
        if not isinstance(ctx, dict):
            ctx = {}
            state["context"] = ctx

        self.guardrails.detect_injection(query)

        broad_review_examples = (
            "what can i improve", "what needs attention", "where should i focus",
            "what should i prioritise", "what should i prioritize", "operational review",
            "what looks risky",
        )
        is_broad_review = any(example in query.lower() for example in broad_review_examples)
        prompt = (
            "Classify this industrial operations question. Return JSON matching the schema.\n"
            "Use general for broad portfolio-review questions asking what to improve, prioritise, "
            "review, or investigate across a site. Broad wording alone is not ambiguity and must not "
            "trigger clarification. Only request clarification when a named asset or site could resolve "
            "to multiple materially different records. Missing evidence is handled after retrieval.\n"
            "Extract explicit asset tags, site names, timeframes, and objectives without inventing them.\n"
            f"Broad portfolio review: {is_broad_review}.\nQuestion: {query}"
        )

        classification: QueryClassification = await self.llm.call_structured(
            prompt, QueryClassification
        )

        ctx["intent"] = classification.intent
        ctx["extracted_entities"] = classification.entities
        ctx["query_time_range"] = classification.time_range

        # Resolve a bounded number of extracted asset mentions through the
        # governed tool layer. Ambiguous results become clarification prompts
        # instead of guessed asset IDs.
        resolved_entities: list[ResolvedEntity] = []
        ambiguity_messages: list[str] = []
        if self._mcp_server is not None:
            for mention in classification.entities[:3]:
                result = await self.call_tool(
                    MCPToolName.RESOLVE_ASSET_TAG,
                    {
                        "mention": mention,
                        "site_id": ctx.get("site_id"),
                        "organisation_id": ctx.get("org_id"),
                    },
                    state=state,
                )
                if not isinstance(result, dict):
                    continue
                if result.get("resolved"):
                    for entity in result.get("entities", [])[:3]:
                        resolved_entities.append(
                            ResolvedEntity(
                                original_text=mention,
                                entity_id=str(entity.get("entity_id", "")),
                                entity_type=str(entity.get("entity_type", "asset")),
                                confidence=float(entity.get("confidence", 0.0)),
                                canonical_name=str(
                                    entity.get("canonical_name") or entity.get("entity_id", mention)
                                ),
                                metadata=dict(entity.get("metadata", {})),
                            )
                        )
                elif result.get("ambiguity_reason"):
                    ambiguity_messages.append(str(result["ambiguity_reason"]))

        if resolved_entities:
            ctx["resolved_entities"] = resolved_entities
            state["resolved_entities"] = resolved_entities
        if ambiguity_messages:
            classification.clarification_needed = True
            classification.clarification_questions.extend(ambiguity_messages)

        if classification.site_context and not ctx.get("site_id"):
            ctx["site_id"] = classification.site_context

        # Clarification path: when the LLM detects ambiguity
        if classification.clarification_needed and classification.clarification_questions:
            ctx["clarification_required"] = True
            ctx["clarification_questions"] = classification.clarification_questions
            logger.info(
                f"Clarification required: {len(classification.clarification_questions)} "
                f"questions for entities={classification.entities}"
            )
        else:
            ctx["clarification_required"] = False
            ctx["clarification_questions"] = []

        state["context"] = ctx

        logger.info(
            f"Query classified: intent={classification.intent}, "
            f"entities={classification.entities}, confidence={classification.confidence}, "
            f"clarification_needed={classification.clarification_needed}"
        )

        return state
