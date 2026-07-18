"""Tests for the Model Router.

Covers task-aware routing, fallback, health monitoring, and latency tracking.
"""

from __future__ import annotations

from mnemos.agentic.runtime.model_router import (
    _FAST_MODEL_TASKS,
    _PRIMARY_MODEL_TASKS,
    ModelRouter,
    ModelTier,
    RouteDecision,
)

# =====================================================================
# Test: RouteDecision
# =====================================================================


class TestRouteDecision:
    def test_decision_creation(self):
        d = RouteDecision(
            tier=ModelTier.FAST,
            model_name="llama3-8b-8192",
            reason="Test",
        )
        assert d.tier == ModelTier.FAST
        assert d.fallback_used is False

    def test_decision_with_fallback(self):
        d = RouteDecision(
            tier=ModelTier.FAST,
            model_name="llama3-8b-8192",
            reason="Fallback",
            fallback_used=True,
        )
        assert d.fallback_used is True


# =====================================================================
# Test: ModelTier enum
# =====================================================================


class TestModelTier:
    def test_all_tiers(self):
        tiers = [t.value for t in ModelTier]
        assert sorted(tiers) == ["auto", "fast", "primary"]


# =====================================================================
# Test: ModelRouter
# =====================================================================


class TestModelRouter:
    def setup_method(self):
        self.router = ModelRouter(
            fast_model_name="llama3-8b-8192",
            primary_model_name="llama3-70b-8192",
        )

    def test_route_fast_task(self):
        decision = self.router.route("query_classification")
        assert decision.tier == ModelTier.FAST
        assert decision.model_name == "llama3-8b-8192"

    def test_route_primary_task(self):
        decision = self.router.route("rca_analysis")
        assert decision.tier == ModelTier.PRIMARY
        assert decision.model_name == "llama3-70b-8192"

    def test_route_unknown_task_defaults_primary(self):
        decision = self.router.route("unknown_task_type")
        assert decision.tier == ModelTier.PRIMARY
        assert decision.model_name == "llama3-70b-8192"

    def test_route_explicit_fast_hint(self):
        decision = self.router.route(
            "rca_analysis",
            tier_hint=ModelTier.FAST,
        )
        assert decision.tier == ModelTier.FAST
        assert decision.model_name == "llama3-8b-8192"

    def test_route_explicit_primary_hint(self):
        decision = self.router.route(
            "query_classification",
            tier_hint=ModelTier.PRIMARY,
        )
        assert decision.tier == ModelTier.PRIMARY
        assert decision.model_name == "llama3-70b-8192"

    def test_fallback_when_primary_unhealthy(self):
        self.router.mark_unhealthy(ModelTier.PRIMARY)
        decision = self.router.route("rca_analysis")
        assert decision.fallback_used is True
        assert decision.tier == ModelTier.FAST

    def test_fallback_when_fast_unhealthy(self):
        self.router.mark_unhealthy(ModelTier.FAST)
        decision = self.router.route("query_classification")
        assert decision.tier == ModelTier.PRIMARY
        assert decision.model_name == "llama3-70b-8192"

    def test_both_unhealthy_uses_fast(self):
        self.router.mark_unhealthy(ModelTier.PRIMARY)
        self.router.mark_unhealthy(ModelTier.FAST)
        decision = self.router.route("query_classification")
        assert decision.fallback_used is True
        assert decision.tier == ModelTier.FAST

    def test_mark_healthy_restores(self):
        self.router.mark_unhealthy(ModelTier.PRIMARY)
        self.router.mark_healthy(ModelTier.PRIMARY)
        decision = self.router.route("rca_analysis")
        assert decision.fallback_used is False

    def test_call_counts(self):
        self.router.route("query_classification")
        self.router.route("query_classification")
        self.router.route("rca_analysis")

        s = self.router.summary()
        assert s["fast_calls"] == 2
        assert s["primary_calls"] == 1

    def test_fallback_count(self):
        self.router.mark_unhealthy(ModelTier.PRIMARY)
        self.router.route("rca_analysis")
        self.router.route("report_synthesis")

        s = self.router.summary()
        assert s["fallback_count"] == 2

    def test_latency_tracking(self):
        self.router.record_latency(ModelTier.FAST, 50.0)
        self.router.record_latency(ModelTier.FAST, 100.0)
        self.router.record_latency(ModelTier.PRIMARY, 200.0)

        assert self.router.get_avg_latency(ModelTier.FAST) == 75.0
        assert self.router.get_avg_latency(ModelTier.PRIMARY) == 200.0

    def test_latency_window_limit(self):
        for i in range(150):
            self.router.record_latency(ModelTier.FAST, float(i))
        avg = self.router.get_avg_latency(ModelTier.FAST)
        assert avg > 0

    def test_summary(self):
        self.router.route("query_classification")
        self.router.route("rca_analysis")
        s = self.router.summary()
        assert s["fast_model"] == "llama3-8b-8192"
        assert s["primary_model"] == "llama3-70b-8192"
        assert s["fast_healthy"] is True
        assert s["primary_healthy"] is True
        assert s["fast_calls"] == 1
        assert s["primary_calls"] == 1

    def test_all_fast_tasks_route_to_fast(self):
        for task in _FAST_MODEL_TASKS:
            decision = self.router.route(task)
            assert decision.tier == ModelTier.FAST, f"Task '{task}' should route to fast"

    def test_all_primary_tasks_route_to_primary(self):
        for task in _PRIMARY_MODEL_TASKS:
            decision = self.router.route(task)
            assert decision.tier == ModelTier.PRIMARY, f"Task '{task}' should route to primary"

    def test_case_insensitive_task(self):
        decision = self.router.route("Query_Classification")
        assert decision.tier == ModelTier.FAST

    def test_hyphenated_task(self):
        decision = self.router.route("query-classification")
        assert decision.tier == ModelTier.FAST
