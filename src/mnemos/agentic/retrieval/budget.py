"""Retrieval Budget Optimiser.

Tracks token and candidate budgets across retrieval strategies to
prevent over-retrieval and optimise resource allocation.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    RetrievalPlan,
    RetrievalStrategy,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("budget_optimizer")

# Estimated token costs per strategy (per candidate)
STRATEGY_TOKEN_COSTS: dict[str, int] = {
    RetrievalStrategy.VECTOR_SEARCH: 200,
    RetrievalStrategy.LEXICAL_SEARCH: 100,
    RetrievalStrategy.GRAPH_TRAVERSAL: 500,
    RetrievalStrategy.SQL_QUERY: 150,
    RetrievalStrategy.METADATA_FILTER: 50,
    RetrievalStrategy.MULTI_HOP: 800,
    RetrievalStrategy.QUERY_DECOMPOSITION: 300,
}


class RetrievalBudgetOptimiser:
    """Manages retrieval budgets across strategies.

    Allocates budget proportionally to strategies and tracks usage.
    Stops early if budget is exhausted.
    """

    def __init__(
        self,
        max_total_candidates: int = 100,
        budget_tokens: int | None = None,
    ) -> None:
        self.max_total_candidates = max_total_candidates
        self.budget_tokens = budget_tokens
        self._candidates_used = 0
        self._tokens_used = 0
        self._strategy_usage: dict[str, int] = {}

    @classmethod
    def from_plan(cls, plan: RetrievalPlan) -> RetrievalBudgetOptimiser:
        return cls(
            max_total_candidates=plan.max_total_candidates,
            budget_tokens=plan.budget_tokens,
        )

    def allocate_per_strategy(self, plan: RetrievalPlan) -> dict[str, int]:
        """Allocate candidate budget per strategy."""
        active_strategies = [s for s in plan.strategies if s != RetrievalStrategy.RERANKING]
        if not active_strategies:
            return {}

        # Weight strategies by their typical cost
        total_weight = sum(STRATEGY_TOKEN_COSTS.get(s.value, 100) for s in active_strategies)
        allocation: dict[str, int] = {}
        remaining = self.max_total_candidates

        for idx, strategy in enumerate(active_strategies):
            weight = STRATEGY_TOKEN_COSTS.get(strategy.value, 100)
            if idx == len(active_strategies) - 1:
                allocation[strategy.value] = remaining
            else:
                count = max(
                    5,
                    int(self.max_total_candidates * weight / total_weight),
                )
                allocation[strategy.value] = min(count, remaining)
                remaining -= allocation[strategy.value]

        return allocation

    def can_add_candidates(self, strategy: str, count: int) -> bool:
        """Check if we can add more candidates within budget."""
        new_total = self._candidates_used + count
        if new_total > self.max_total_candidates:
            return False

        if self.budget_tokens is not None:
            strategy_cost = STRATEGY_TOKEN_COSTS.get(strategy, 100)
            estimated_tokens = count * strategy_cost
            if self._tokens_used + estimated_tokens > self.budget_tokens:
                return False

        return True

    def record_usage(self, strategy: str, candidates: int, tokens: int = 0) -> None:
        """Record resource usage."""
        self._candidates_used += candidates
        self._tokens_used += tokens
        self._strategy_usage[strategy] = self._strategy_usage.get(strategy, 0) + candidates

    def trim_bundle(self, bundle: EvidenceBundle) -> None:
        """Trim bundle to fit within budget if necessary."""
        total = len(bundle.raw_vector_data)
        if total <= self.max_total_candidates:
            return

        # Sort by score and keep top candidates
        bundle.raw_vector_data.sort(
            key=lambda x: x.get("rerank_score", x.get("score", 0.0)),
            reverse=True,
        )
        excess = total - self.max_total_candidates
        bundle.raw_vector_data = bundle.raw_vector_data[:-excess]
        logger.info(f"Trimmed {excess} candidates to fit budget")

    @property
    def usage_summary(self) -> dict[str, Any]:
        return {
            "candidates_used": self._candidates_used,
            "candidates_budget": self.max_total_candidates,
            "tokens_used": self._tokens_used,
            "tokens_budget": self.budget_tokens,
            "per_strategy": dict(self._strategy_usage),
        }
