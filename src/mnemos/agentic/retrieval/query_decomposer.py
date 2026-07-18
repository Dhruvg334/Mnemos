"""Query Decomposer.

Uses the LLM to break complex industrial queries into simpler sub-queries
that can each be independently retrieved. Supports multi-hop reasoning by
identifying dependency chains between sub-queries.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mnemos.agentic.schemas.base import (
    QueryIntent,
    SubQuery,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("query_decomposer")


class DecompositionOutput(BaseModel):
    """Structured LLM output for query decomposition."""

    needs_decomposition: bool = Field(
        description="True if the query is complex enough to warrant decomposition.",
    )
    sub_queries: list[str] = Field(
        default_factory=list,
        description="Ordered list of sub-query texts.",
    )
    reasoning: str = Field(default="")
    dependency_indices: list[list[int]] = Field(
        default_factory=list,
        description="dependency_indices[i] lists indices of sub-queries that sub-query i depends on.",
    )


class QueryDecomposer:
    """Decomposes complex queries into retrievable sub-queries.

    Uses the LLM to:
    1. Determine if decomposition is needed
    2. Break the query into atomic sub-queries
    3. Identify dependency chains between sub-queries
    """

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def decompose(
        self,
        query: str,
        intent: QueryIntent,
        entities: list[str],
    ) -> list[SubQuery]:
        """Decompose a query into sub-queries if needed."""
        prompt = self._build_prompt(query, intent, entities)

        try:
            output: DecompositionOutput = await self.llm.call_structured(
                prompt, DecompositionOutput
            )
        except Exception as exc:
            logger.warning(f"LLM decomposition failed ({exc}), returning original query")
            return [
                SubQuery(
                    original_query=query,
                    sub_query_text=query,
                    decomposition_reasoning="LLM decomposition failed, using original",
                    priority=0,
                )
            ]

        if not output.needs_decomposition or not output.sub_queries:
            logger.info("Query does not need decomposition")
            return [
                SubQuery(
                    original_query=query,
                    sub_query_text=query,
                    decomposition_reasoning=output.reasoning
                    or "Simple query, no decomposition needed",
                    priority=0,
                )
            ]

        sub_queries: list[SubQuery] = []
        for idx, sq_text in enumerate(output.sub_queries):
            deps = output.dependency_indices[idx] if idx < len(output.dependency_indices) else []
            sub_queries.append(
                SubQuery(
                    original_query=query,
                    sub_query_text=sq_text,
                    decomposition_reasoning=output.reasoning,
                    priority=idx,
                    depends_on=deps,
                )
            )

        logger.info(
            f"Decomposed query into {len(sub_queries)} sub-queries: "
            f"{[sq.sub_query_text[:50] for sq in sub_queries]}"
        )
        return sub_queries

    def _build_prompt(self, query: str, intent: QueryIntent, entities: list[str]) -> str:
        entity_str = ", ".join(entities) if entities else "none detected"
        return (
            "You are an industrial query decomposer. Analyse the query below "
            "and decide if it should be decomposed into simpler sub-queries.\n\n"
            f"Query: '{query}'\n"
            f"Intent: {intent.value}\n"
            f"Detected entities: {entity_str}\n\n"
            "Rules:\n"
            "- Only decompose if the query asks about multiple distinct aspects "
            "(e.g. 'What is the pressure limit AND when was it last inspected?')\n"
            "- Each sub-query should be independently answerable from the knowledge base\n"
            "- Order sub-queries so dependencies are satisfied\n"
            "- Keep sub-queries specific and focused\n"
            "- If the query is already atomic, set needs_decomposition=false\n\n"
            "Return a JSON object matching the DecompositionOutput schema."
        )
