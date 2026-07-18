"""Model Router for the Mnemos agentic runtime.

Routes LLM calls to the appropriate model based on task complexity:
- fast_llm (8B): classification, query routing, simple extraction
- primary_llm (70B): RCA analysis, report composition, complex reasoning

Provides:
- ModelRouter: task-aware routing with fallback
- ModelTier: enum for model tiers
- RouteDecision: routing decision with reasoning
"""

from __future__ import annotations

import time
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("runtime.model_router")


class ModelTier(StrEnum):
    """Model tiers for routing."""

    FAST = "fast"
    PRIMARY = "primary"
    AUTO = "auto"


class RouteDecision(BaseModel):
    """Decision from the model router."""

    tier: ModelTier
    model_name: str
    reason: str
    fallback_used: bool = False
    latency_ms: float = 0.0


# Tasks that are well-suited for the fast (smaller) model
_FAST_MODEL_TASKS: set[str] = {
    "query_classification",
    "query_routing",
    "ambiguity_detection",
    "simple_extraction",
    "text_summarization",
    "confidence_scoring",
    "source_reliability",
    "metadata_extraction",
    "keyword_extraction",
    "intent_detection",
}

# Tasks that require the primary (larger) model
_PRIMARY_MODEL_TASKS: set[str] = {
    "rca_analysis",
    "rca_hypothesis_generation",
    "rca_root_cause_identification",
    "report_synthesis",
    "report_composition",
    "compliance_analysis",
    "compliance_gap_analysis",
    "reasoning_chain",
    "multi_hop_reasoning",
    "evidence_interpretation",
    "hypothesis_generation",
    "anomaly_analysis",
    "knowledge_card_generation",
    "procedure_review",
}


class ModelRouter:
    """Routes LLM calls to appropriate models based on task type.

    Provides:
    - Task-aware routing (fast vs primary model)
    - Automatic fallback on failure
    - Latency tracking for adaptive routing
    - Health monitoring per model tier

    Usage:
        router = ModelRouter(fast_llm_config, primary_llm_config)
        decision = router.route("query_classification")
        # Use decision.model_name to select the LLM client
    """

    def __init__(
        self,
        fast_model_name: str = "llama3-8b-8192",
        primary_model_name: str = "llama3-70b-8192",
        default_tier: ModelTier = ModelTier.AUTO,
    ) -> None:
        self._fast_model = fast_model_name
        self._primary_model = primary_model_name
        self._default_tier = default_tier

        self._fast_healthy = True
        self._primary_healthy = True

        self._fast_latencies: list[float] = []
        self._primary_latencies: list[float] = []

        self._call_counts: dict[str, int] = {
            ModelTier.FAST: 0,
            ModelTier.PRIMARY: 0,
        }
        self._fallback_count = 0

    def route(
        self,
        task_type: str,
        *,
        tier_hint: ModelTier | None = None,
        context: dict[str, Any] | None = None,
    ) -> RouteDecision:
        """Route a task to the appropriate model.

        Args:
            task_type: Type of LLM task (e.g., "query_classification")
            tier_hint: Optional explicit tier override
            context: Optional context for routing decisions

        Returns:
            RouteDecision with selected model and reasoning
        """
        start = time.time()

        if tier_hint and tier_hint != ModelTier.AUTO:
            model_name = self._fast_model if tier_hint == ModelTier.FAST else self._primary_model
            return RouteDecision(
                tier=tier_hint,
                model_name=model_name,
                reason=f"Explicit tier hint: {tier_hint.value}",
            )

        task_lower = task_type.lower().replace(" ", "_").replace("-", "_")

        if task_lower in _FAST_MODEL_TASKS:
            if self._fast_healthy:
                self._call_counts[ModelTier.FAST] += 1
                latency = (time.time() - start) * 1000
                return RouteDecision(
                    tier=ModelTier.FAST,
                    model_name=self._fast_model,
                    reason=f"Task '{task_type}' matched fast model tasks",
                    latency_ms=latency,
                )

        if task_lower in _PRIMARY_MODEL_TASKS:
            if self._primary_healthy:
                self._call_counts[ModelTier.PRIMARY] += 1
                latency = (time.time() - start) * 1000
                return RouteDecision(
                    tier=ModelTier.PRIMARY,
                    model_name=self._primary_model,
                    reason=f"Task '{task_type}' matched primary model tasks",
                    latency_ms=latency,
                )

        if self._primary_healthy:
            self._call_counts[ModelTier.PRIMARY] += 1
            latency = (time.time() - start) * 1000
            return RouteDecision(
                tier=ModelTier.PRIMARY,
                model_name=self._primary_model,
                reason=f"Unknown task '{task_type}', defaulting to primary",
                latency_ms=latency,
            )

        if self._fast_healthy:
            self._call_counts[ModelTier.FAST] += 1
            self._fallback_count += 1
            latency = (time.time() - start) * 1000
            return RouteDecision(
                tier=ModelTier.FAST,
                model_name=self._fast_model,
                reason="Fallback to fast model (primary unhealthy)",
                fallback_used=True,
                latency_ms=latency,
            )

        latency = (time.time() - start) * 1000
        return RouteDecision(
            tier=ModelTier.FAST,
            model_name=self._fast_model,
            reason="Both models unhealthy, using fast as last resort",
            fallback_used=True,
            latency_ms=latency,
        )

    def record_latency(self, tier: ModelTier, latency_ms: float) -> None:
        """Record a call latency for adaptive routing."""
        if tier == ModelTier.FAST:
            self._fast_latencies.append(latency_ms)
            if len(self._fast_latencies) > 100:
                self._fast_latencies = self._fast_latencies[-100:]
        else:
            self._primary_latencies.append(latency_ms)
            if len(self._primary_latencies) > 100:
                self._primary_latencies = self._primary_latencies[-100:]

    def mark_unhealthy(self, tier: ModelTier) -> None:
        """Mark a model tier as unhealthy (triggers fallback)."""
        if tier == ModelTier.FAST:
            self._fast_healthy = False
            logger.warning("Fast model marked unhealthy")
        else:
            self._primary_healthy = False
            logger.warning("Primary model marked unhealthy")

    def mark_healthy(self, tier: ModelTier) -> None:
        """Mark a model tier as healthy again."""
        if tier == ModelTier.FAST:
            self._fast_healthy = True
        else:
            self._primary_healthy = True

    def get_avg_latency(self, tier: ModelTier) -> float:
        """Get average latency for a tier."""
        latencies = self._fast_latencies if tier == ModelTier.FAST else self._primary_latencies
        if not latencies:
            return 0.0
        return sum(latencies) / len(latencies)

    def summary(self) -> dict[str, Any]:
        """Summary of router state."""
        return {
            "fast_model": self._fast_model,
            "primary_model": self._primary_model,
            "fast_healthy": self._fast_healthy,
            "primary_healthy": self._primary_healthy,
            "fast_calls": self._call_counts[ModelTier.FAST],
            "primary_calls": self._call_counts[ModelTier.PRIMARY],
            "fallback_count": self._fallback_count,
            "fast_avg_latency_ms": round(self.get_avg_latency(ModelTier.FAST), 2),
            "primary_avg_latency_ms": round(self.get_avg_latency(ModelTier.PRIMARY), 2),
        }
