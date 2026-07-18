"""Comprehensive tests for observability, streaming, and optimization modules.

Covers ObservabilityDashboard, StreamingSupervisor (progress events),
ResponseCache, BatchRetrievalManager, ParallelExecutor,
TimeoutRecoveryManager, and ProductionOptimizer.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from mnemos.agentic.runtime.audit import AuditLogger
from mnemos.agentic.runtime.events import InvestigationEventLog
from mnemos.agentic.runtime.observability import ObservabilityDashboard
from mnemos.agentic.runtime.optimizations import (
    BatchRetrievalManager,
    ParallelExecutor,
    ProductionOptimizer,
    ResponseCache,
    TimeoutRecoveryManager,
    _hash_cache_key,
)
from mnemos.agentic.runtime.streaming import (
    InvestigationProgressEvent,
    _merge_state,
    _phase_str,
)
from mnemos.agentic.runtime.types import (
    EventType,
    InvestigationPhase,
)
from mnemos.agentic.schemas.base import AuditAction

# ======================================================================
# Helpers
# ======================================================================


def _make_event_log(events: list[tuple] | None = None) -> InvestigationEventLog:
    """Build an InvestigationEventLog optionally pre-loaded with events.

    Each tuple is (event_type, phase, agent_name, data).
    """
    log = InvestigationEventLog("test_investigation")
    if events:
        for etype, phase, agent, data in events:
            log.append(
                event_type=etype,
                phase=phase,
                agent_name=agent,
                data=data or {},
            )
    return log


def _make_audit_log(entries: list[dict] | None = None) -> AuditLogger:
    """Build an AuditLogger optionally pre-loaded with entries."""
    logger = AuditLogger("test_investigation")
    if entries:
        for e in entries:
            logger.log(
                action=e.get("action", AuditAction.TOOL_CALLED),
                agent_name=e.get("agent_name"),
                tool_name=e.get("tool_name"),
                success=e.get("success", True),
                error=e.get("error"),
                duration_ms=e.get("duration_ms", 0.0),
                input_data=e.get("input_data", {}),
                output_data=e.get("output_data", {}),
                metadata=e.get("metadata", {}),
            )
    return logger


# ======================================================================
# ObservabilityDashboard
# ======================================================================


class TestObservabilityDashboard:
    """Tests for the ObservabilityDashboard class."""

    def test_empty_dashboard(self) -> None:
        """Dashboard with no events or audit entries returns safe defaults."""
        event_log = _make_event_log()
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        assert dash.get_active_agents() == []
        assert dash.get_tool_usage()["total_calls"] == 0
        assert dash.get_agent_timings()["overall_avg_ms"] == 0.0
        assert dash.get_confidence_evolution() == []
        assert dash.get_retrieval_statistics()["total_candidates_found"] == 0

    def test_active_agents_none_running(self) -> None:
        """No agent events -> active agents list is empty."""
        event_log = _make_event_log()
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        assert dash.get_active_agents() == []

    def test_active_agents_with_events(self) -> None:
        """Agents with AGENT_INVOKED events show as 'running'."""
        event_log = _make_event_log(
            [
                (
                    EventType.AGENT_INVOKED,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    "retrieval_agent",
                    {},
                ),
                (EventType.AGENT_INVOKED, InvestigationPhase.ANALYSIS, "analysis_agent", {}),
                (EventType.AGENT_COMPLETED, InvestigationPhase.ANALYSIS, "analysis_agent", {}),
            ]
        )
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        active = dash.get_active_agents()

        # retrieval_agent last seen as INVOKED -> running
        retrieval = next(a for a in active if a["agent_name"] == "retrieval_agent")
        assert retrieval["status"] == "running"

        # analysis_agent last seen as COMPLETED -> completed
        analysis = next(a for a in active if a["agent_name"] == "analysis_agent")
        assert analysis["status"] == "completed"

    def test_tool_usage_empty(self) -> None:
        """No tool calls in audit -> empty stats."""
        event_log = _make_event_log()
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        usage = dash.get_tool_usage()
        assert usage["tools"] == {}
        assert usage["total_calls"] == 0
        assert usage["overall_success_rate"] == 0.0
        assert usage["overall_error_rate"] == 0.0

    def test_tool_usage_with_entries(self) -> None:
        """Tool calls in audit produce correct counts and success rates."""
        audit = _make_audit_log(
            [
                {
                    "tool_name": "web_search",
                    "action": AuditAction.TOOL_CALLED,
                    "success": True,
                    "duration_ms": 100.0,
                },
                {
                    "tool_name": "web_search",
                    "action": AuditAction.TOOL_CALLED,
                    "success": True,
                    "duration_ms": 200.0,
                },
                {
                    "tool_name": "web_search",
                    "action": AuditAction.TOOL_CALLED,
                    "success": False,
                    "error": "timeout",
                    "duration_ms": 300.0,
                },
                {
                    "tool_name": "db_query",
                    "action": AuditAction.TOOL_CALLED,
                    "success": True,
                    "duration_ms": 50.0,
                },
            ]
        )
        event_log = _make_event_log()
        dash = ObservabilityDashboard(event_log, audit)

        usage = dash.get_tool_usage()
        assert usage["total_calls"] == 4
        ws = usage["tools"]["web_search"]
        assert ws["call_count"] == 3
        assert ws["success_count"] == 2
        assert ws["failure_count"] == 1
        assert ws["success_rate"] == pytest.approx(2 / 3)
        assert ws["avg_duration_ms"] == pytest.approx(200.0)
        assert ws["min_duration_ms"] == pytest.approx(100.0)
        assert ws["max_duration_ms"] == pytest.approx(300.0)
        assert usage["overall_success_rate"] == pytest.approx(3 / 4)

    def test_workflow_graph_empty(self) -> None:
        """No phase changes -> minimal graph."""
        event_log = _make_event_log()
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        graph = dash.get_workflow_graph()
        assert graph["current_phase"] == InvestigationPhase.INITIALIZATION
        assert graph["total_transitions"] == 0
        assert graph["edges_traversed"] == []

    def test_workflow_graph_with_transitions(self) -> None:
        """Multiple phase changes produce correct DAG edges."""
        event_log = _make_event_log(
            [
                (EventType.INVESTIGATION_STARTED, InvestigationPhase.INITIALIZATION, None, {}),
                (EventType.PHASE_CHANGED, InvestigationPhase.EVIDENCE_GATHERING, None, {}),
                (EventType.PHASE_CHANGED, InvestigationPhase.ANALYSIS, None, {}),
                (EventType.PHASE_CHANGED, InvestigationPhase.VERIFICATION, None, {}),
            ]
        )
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        graph = dash.get_workflow_graph()
        assert graph["current_phase"] == InvestigationPhase.VERIFICATION
        assert graph["total_transitions"] == 3
        assert len(graph["nodes_visited"]) == 4
        assert graph["edges_traversed"][0]["to"] == InvestigationPhase.EVIDENCE_GATHERING

    def test_agent_timings_empty(self) -> None:
        """No timing data -> zero values."""
        event_log = _make_event_log()
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        timings = dash.get_agent_timings()
        assert timings["agents"] == {}
        assert timings["overall_avg_ms"] == 0.0
        assert timings["overall_p50_ms"] == 0.0
        assert timings["overall_p95_ms"] == 0.0

    def test_agent_timings_with_data(self) -> None:
        """Agent metadata with execution times produces correct percentiles."""
        durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        audit = _make_audit_log(
            [
                {
                    "agent_name": "retrieval_agent",
                    "action": AuditAction.AGENT_COMPLETED,
                    "duration_ms": d,
                }
                for d in durations
            ]
        )
        event_log = _make_event_log()
        dash = ObservabilityDashboard(event_log, audit)

        timings = dash.get_agent_timings()
        ra = timings["agents"]["retrieval_agent"]
        assert ra["call_count"] == 10
        assert ra["avg_ms"] == pytest.approx(55.0)
        assert ra["min_ms"] == pytest.approx(10.0)
        assert ra["max_ms"] == pytest.approx(100.0)
        assert timings["overall_avg_ms"] == pytest.approx(55.0)

    def test_confidence_evolution_empty(self) -> None:
        """No confidence data -> empty list."""
        event_log = _make_event_log()
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        assert dash.get_confidence_evolution() == []

    def test_confidence_evolution_with_data(self) -> None:
        """Confidence values tracked over iterations from AGENT_COMPLETED events."""
        event_log = _make_event_log(
            [
                (
                    EventType.SUPERVISOR_DECISION,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    None,
                    {"from_iteration": 1},
                ),
                (
                    EventType.AGENT_COMPLETED,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    "retrieval_agent",
                    {"confidence": 0.6},
                ),
                (
                    EventType.SUPERVISOR_DECISION,
                    InvestigationPhase.ANALYSIS,
                    None,
                    {"from_iteration": 2},
                ),
                (
                    EventType.AGENT_COMPLETED,
                    InvestigationPhase.ANALYSIS,
                    "analysis_agent",
                    {"confidence": 0.85},
                ),
            ]
        )
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        evo = dash.get_confidence_evolution()
        assert len(evo) == 2
        assert evo[0]["iteration"] == 1
        assert evo[0]["confidence"] == pytest.approx(0.6)
        assert evo[0]["agent_name"] == "retrieval_agent"
        assert evo[1]["iteration"] == 2
        assert evo[1]["confidence"] == pytest.approx(0.85)

    def test_retrieval_statistics_empty(self) -> None:
        """No retrieval data -> zero values."""
        event_log = _make_event_log()
        audit = _make_audit_log()
        dash = ObservabilityDashboard(event_log, audit)

        stats = dash.get_retrieval_statistics()
        assert stats["strategies_used"] == []
        assert stats["total_candidates_found"] == 0
        assert stats["verified_count"] == 0
        assert stats["avg_confidence"] == 0.0

    def test_dashboard_snapshot(self) -> None:
        """Complete snapshot includes all sections."""
        event_log = _make_event_log(
            [
                (EventType.INVESTIGATION_STARTED, InvestigationPhase.INITIALIZATION, None, {}),
                (
                    EventType.AGENT_INVOKED,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    "retrieval_agent",
                    {},
                ),
                (
                    EventType.AGENT_COMPLETED,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    "retrieval_agent",
                    {"confidence": 0.7},
                ),
                (
                    EventType.EVIDENCE_COLLECTED,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    "retrieval_agent",
                    {"count": 5, "strategies": ["semantic", "keyword"], "avg_confidence": 0.75},
                ),
                (EventType.PHASE_CHANGED, InvestigationPhase.ANALYSIS, None, {}),
                (
                    EventType.AGENT_COMPLETED,
                    InvestigationPhase.ANALYSIS,
                    "analysis_agent",
                    {"confidence": 0.9},
                ),
                (
                    EventType.INVESTIGATION_COMPLETED,
                    InvestigationPhase.COMPLETION,
                    None,
                    {"reason": "sufficient_evidence"},
                ),
            ]
        )
        audit = _make_audit_log(
            [
                {
                    "tool_name": "web_search",
                    "action": AuditAction.TOOL_CALLED,
                    "success": True,
                    "duration_ms": 120.0,
                },
                {
                    "agent_name": "retrieval_agent",
                    "action": AuditAction.AGENT_COMPLETED,
                    "duration_ms": 500.0,
                },
            ]
        )
        dash = ObservabilityDashboard(event_log, audit)

        snap = dash.get_dashboard_snapshot()
        assert "investigation_id" in snap
        assert "event_summary" in snap
        assert "audit_summary" in snap
        assert "active_agents" in snap
        assert "tool_usage" in snap
        assert "workflow_graph" in snap
        assert "agent_timings" in snap
        assert "confidence_evolution" in snap
        assert "retrieval_statistics" in snap
        assert "investigation_summary" in snap
        assert snap["investigation_id"] == "test_investigation"

    def test_investigation_summary(self) -> None:
        """Summary includes phases, agents, errors."""
        event_log = _make_event_log(
            [
                (EventType.INVESTIGATION_STARTED, InvestigationPhase.INITIALIZATION, None, {}),
                (
                    EventType.AGENT_INVOKED,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    "retrieval_agent",
                    {},
                ),
                (
                    EventType.AGENT_COMPLETED,
                    InvestigationPhase.EVIDENCE_GATHERING,
                    "retrieval_agent",
                    {},
                ),
                (EventType.AGENT_INVOKED, InvestigationPhase.ANALYSIS, "analysis_agent", {}),
                (
                    EventType.AGENT_FAILED,
                    InvestigationPhase.ANALYSIS,
                    "analysis_agent",
                    {"error": "LLM timeout"},
                ),
                (EventType.APPROVAL_REQUESTED, InvestigationPhase.APPROVAL, "supervisor_agent", {}),
                (
                    EventType.REFLECTION_COMPLETED,
                    InvestigationPhase.REFLECTION,
                    "reflection_agent",
                    {},
                ),
                (
                    EventType.INVESTIGATION_COMPLETED,
                    InvestigationPhase.COMPLETION,
                    None,
                    {"reason": "done"},
                ),
            ]
        )
        audit = _make_audit_log(
            [
                {"action": AuditAction.APPROVAL_GRANTED},
                {"action": AuditAction.APPROVAL_DENIED},
            ]
        )
        dash = ObservabilityDashboard(event_log, audit)

        summary = dash.get_investigation_summary()
        assert "initialization" in summary["phases_visited"]
        assert "retrieval_agent" in summary["agents_dispatched"]
        assert "analysis_agent" in summary["agents_failed"]
        assert summary["total_errors"] == 1
        assert summary["approvals_requested"] == 1
        assert summary["approvals_granted"] == 1
        assert summary["approvals_denied"] == 1
        assert summary["reflection_count"] == 1
        assert summary["is_complete"] is True
        assert summary["termination_reason"] == "done"


# ======================================================================
# StreamingSupervisor (progress events and helpers)
# ======================================================================


class TestStreamingHelpers:
    """Tests for streaming helper functions and progress event model."""

    def test_progress_event_creation(self) -> None:
        """Create an InvestigationProgressEvent with all fields."""
        event = InvestigationProgressEvent(
            event_type="phase_start",
            phase="evidence_gathering",
            agent_name="retrieval_agent",
            iteration=2,
            data={"detail": "test"},
        )
        assert event.event_type == "phase_start"
        assert event.phase == "evidence_gathering"
        assert event.agent_name == "retrieval_agent"
        assert event.iteration == 2
        assert event.data == {"detail": "test"}
        assert event.timestamp  # auto-generated

    def test_progress_event_defaults(self) -> None:
        """InvestigationProgressEvent has sensible defaults."""
        event = InvestigationProgressEvent(
            event_type="workflow_complete",
            phase="completion",
        )
        assert event.agent_name is None
        assert event.iteration == 0
        assert event.data == {}

    def test_merge_state_list_extend(self) -> None:
        """_merge_state extends list fields."""
        target = {"evidence": [{"a": 1}], "errors": []}
        source = {"evidence": [{"b": 2}]}
        _merge_state(target, source)
        assert target["evidence"] == [{"a": 1}, {"b": 2}]
        assert target["errors"] == []

    def test_merge_state_dict_update(self) -> None:
        """_merge_state merges dict fields."""
        target = {"agent_outputs": {"a": {"x": 1}}}
        source = {"agent_outputs": {"b": {"y": 2}}}
        _merge_state(target, source)
        assert target["agent_outputs"] == {"a": {"x": 1}, "b": {"y": 2}}

    def test_merge_state_overwrite_scalar(self) -> None:
        """_merge_state overwrites scalar fields."""
        target = {"phase": "old", "iteration": 1}
        source = {"phase": "new"}
        _merge_state(target, source)
        assert target["phase"] == "new"
        assert target["iteration"] == 1

    def test_merge_state_new_key(self) -> None:
        """_merge_state adds new keys."""
        target = {"a": 1}
        source = {"b": 2}
        _merge_state(target, source)
        assert target == {"a": 1, "b": 2}

    def test_phase_str_enum(self) -> None:
        """_phase_str converts InvestigationPhase enum to string."""
        assert _phase_str(InvestigationPhase.ANALYSIS) == "analysis"

    def test_phase_str_passthrough(self) -> None:
        """_phase_str passes through plain strings."""
        assert _phase_str("analysis") == "analysis"

    @pytest.mark.asyncio
    async def test_streaming_yields_start_event(self) -> None:
        """First event yielded by run_streaming is a phase_start."""
        from mnemos.agentic.runtime.registry import AgentRegistry
        from mnemos.agentic.runtime.streaming import StreamingSupervisor

        registry = AgentRegistry()

        supervisor = StreamingSupervisor(
            agent_registry=registry,
            agent_functions={},
            max_iterations=5,
        )

        # Use a mock decision with a real enum for termination_reason
        # so that .value works correctly in the streaming code path.
        term_reason = MagicMock()
        term_reason.value = "sufficient_evidence"

        mock_decision = MagicMock()
        mock_decision.phase = InvestigationPhase.COMPLETION
        mock_decision.should_continue = False
        mock_decision.termination_reason = term_reason
        mock_decision.reasoning = "Test termination"
        mock_decision.agents_to_dispatch = []
        mock_decision.parallel = False

        supervisor._supervisor.decide_next = MagicMock(return_value=mock_decision)

        events = []
        async for event in supervisor.run_streaming("inv_001", "test query"):
            events.append(event)

        assert len(events) >= 2
        assert events[0].event_type == "phase_start"
        assert events[0].phase == InvestigationPhase.INITIALIZATION
        assert events[-1].event_type == "workflow_complete"

    @pytest.mark.asyncio
    async def test_streaming_yields_complete_event(self) -> None:
        """Last event yielded by run_streaming is workflow_complete."""
        from mnemos.agentic.runtime.registry import AgentRegistry
        from mnemos.agentic.runtime.streaming import StreamingSupervisor

        registry = AgentRegistry()

        supervisor = StreamingSupervisor(
            agent_registry=registry,
            agent_functions={},
            max_iterations=5,
        )

        term_reason = MagicMock()
        term_reason.value = "sufficient_evidence"

        mock_decision = MagicMock()
        mock_decision.phase = InvestigationPhase.COMPLETION
        mock_decision.should_continue = False
        mock_decision.termination_reason = term_reason
        mock_decision.reasoning = "Done"
        mock_decision.agents_to_dispatch = []
        mock_decision.parallel = False

        supervisor._supervisor.decide_next = MagicMock(return_value=mock_decision)

        events = []
        async for event in supervisor.run_streaming("inv_002", "query"):
            events.append(event)

        last = events[-1]
        assert last.event_type == "workflow_complete"
        assert last.phase == InvestigationPhase.COMPLETION
        assert "termination_reason" in last.data


# ======================================================================
# ResponseCache
# ======================================================================


class TestResponseCache:
    """Tests for the ResponseCache LRU+TTL cache."""

    def test_cache_put_get(self) -> None:
        """Basic put and get returns stored value."""
        cache = ResponseCache(max_size=10, default_ttl_seconds=60.0)
        cache.put("tool_a", {"q": "hello"}, {"result": 42})

        val = cache.get("tool_a", {"q": "hello"})
        assert val == {"result": 42}

    def test_cache_miss(self) -> None:
        """Get for non-existent key returns None."""
        cache = ResponseCache()
        assert cache.get("tool_a", {"q": "missing"}) is None

    def test_cache_ttl_expiration(self) -> None:
        """Expired entry returns None."""
        cache = ResponseCache(default_ttl_seconds=0.0)
        cache.put("tool_a", {"q": "x"}, "value")

        time.sleep(0.01)
        assert cache.get("tool_a", {"q": "x"}) is None

    def test_cache_lru_eviction(self) -> None:
        """Exceeding max_size evicts oldest entry."""
        cache = ResponseCache(max_size=3, default_ttl_seconds=60.0)
        cache.put("t", {"i": 0}, "v0")
        cache.put("t", {"i": 1}, "v1")
        cache.put("t", {"i": 2}, "v2")
        # Cache full; inserting a new entry should evict i=0
        cache.put("t", {"i": 3}, "v3")

        assert cache.get("t", {"i": 0}) is None
        assert cache.get("t", {"i": 1}) == "v1"
        assert cache.get("t", {"i": 3}) == "v3"

    def test_cache_invalidate_tool(self) -> None:
        """Invalidate removes entries for a specific tool."""
        cache = ResponseCache(default_ttl_seconds=60.0)
        cache.put("web_search", {"q": "a"}, "r1")
        cache.put("web_search", {"q": "b"}, "r2")
        cache.put("db_query", {"q": "c"}, "r3")

        removed = cache.invalidate("web_search")
        assert removed == 2
        assert cache.get("web_search", {"q": "a"}) is None
        assert cache.get("db_query", {"q": "c"}) == "r3"

    def test_cache_invalidate_all(self) -> None:
        """Invalidate with no args clears everything."""
        cache = ResponseCache(default_ttl_seconds=60.0)
        cache.put("a", {"x": 1}, "v1")
        cache.put("b", {"y": 2}, "v2")

        removed = cache.invalidate()
        assert removed == 2
        assert cache.get("a", {"x": 1}) is None
        assert cache.get("b", {"y": 2}) is None

    def test_cache_stats(self) -> None:
        """Hits, misses, and size are tracked correctly."""
        cache = ResponseCache(max_size=10, default_ttl_seconds=60.0)
        cache.put("t", {"q": 1}, "v")
        cache.get("t", {"q": 1})  # hit
        cache.get("t", {"q": 999})  # miss
        cache.get("nonexistent", {"q": 0})  # miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["size"] == 1
        assert stats["max_size"] == 10
        assert stats["hit_rate"] == round(1 / 3, 4)

    def test_cache_cleanup(self) -> None:
        """Cleanup removes only expired entries."""
        cache = ResponseCache(default_ttl_seconds=0.0)
        cache.put("a", {"q": 1}, "v1")
        cache.put("b", {"q": 2}, "v2", ttl_seconds=3600.0)

        time.sleep(0.01)
        removed = cache.cleanup()
        assert removed == 1
        # The long-TTL entry survives
        assert cache.get("b", {"q": 2}) == "v2"

    def test_cache_same_args_same_key(self) -> None:
        """Same tool+args produce the same cache key."""
        key1 = _hash_cache_key("tool", {"a": 1, "b": 2})
        key2 = _hash_cache_key("tool", {"a": 1, "b": 2})
        assert key1 == key2

    def test_cache_different_args_different_key(self) -> None:
        """Different args produce different cache keys."""
        key1 = _hash_cache_key("tool", {"a": 1})
        key2 = _hash_cache_key("tool", {"a": 2})
        assert key1 != key2

    def test_cache_overwrite_same_key(self) -> None:
        """Put with same key updates the value."""
        cache = ResponseCache(default_ttl_seconds=60.0)
        cache.put("t", {"q": 1}, "old")
        cache.put("t", {"q": 1}, "new")
        assert cache.get("t", {"q": 1}) == "new"
        assert cache.stats()["size"] == 1

    def test_cache_get_refreshes_lru(self) -> None:
        """Getting an entry moves it to the end of the LRU order."""
        cache = ResponseCache(max_size=3, default_ttl_seconds=60.0)
        cache.put("t", {"i": 0}, "v0")
        cache.put("t", {"i": 1}, "v1")
        cache.put("t", {"i": 2}, "v2")
        # Access i=0 to refresh it
        cache.get("t", {"i": 0})
        # Now insert i=3; i=1 should be evicted (oldest non-refreshed)
        cache.put("t", {"i": 3}, "v3")

        assert cache.get("t", {"i": 0}) == "v0"
        assert cache.get("t", {"i": 1}) is None

    def test_cache_custom_ttl(self) -> None:
        """Per-entry TTL overrides the default."""
        cache = ResponseCache(default_ttl_seconds=3600.0)
        cache.put("a", {"q": 1}, "short", ttl_seconds=0.0)
        cache.put("b", {"q": 2}, "long")

        time.sleep(0.01)
        assert cache.get("a", {"q": 1}) is None
        assert cache.get("b", {"q": 2}) == "long"

    def test_cache_empty_args(self) -> None:
        """Cache works with empty argument dicts."""
        cache = ResponseCache(default_ttl_seconds=60.0)
        cache.put("t", {}, "value")
        assert cache.get("t", {}) == "value"

    def test_cache_nested_args(self) -> None:
        """Cache works with deeply nested argument dicts."""
        cache = ResponseCache(default_ttl_seconds=60.0)
        args = {"filters": {"categories": ["a", "b"], "min_score": 0.5}}
        cache.put("search", args, "result")
        assert cache.get("search", args) == "result"


# ======================================================================
# BatchRetrievalManager
# ======================================================================


class TestBatchRetrievalManager:
    """Tests for the BatchRetrievalManager batching logic."""

    @pytest.mark.asyncio
    async def test_batch_single_request(self) -> None:
        """Single request completes via batch handler."""
        manager = BatchRetrievalManager(max_batch_size=10, max_wait_seconds=0.05)

        async def handler(reqs):
            return {r.request_id: f"result_{r.request_id}" for r in reqs}

        manager.set_batch_handler(handler)

        result = await manager.add_request("req_1", "query1", "semantic", {})
        assert result == "result_req_1"

    @pytest.mark.asyncio
    async def test_batch_multiple_requests(self) -> None:
        """Multiple requests are batched together."""
        manager = BatchRetrievalManager(max_batch_size=10, max_wait_seconds=0.05)
        received_batches: list[list[str]] = []

        async def handler(reqs):
            received_batches.append([r.request_id for r in reqs])
            return {r.request_id: r.query for r in reqs}

        manager.set_batch_handler(handler)

        # Fire multiple requests concurrently
        results = await asyncio.gather(
            manager.add_request("r1", "q1", "semantic", {}),
            manager.add_request("r2", "q2", "keyword", {}),
            manager.add_request("r3", "q3", "hybrid", {}),
        )

        assert results[0] == "q1"
        assert results[1] == "q2"
        assert results[2] == "q3"
        # All should be in one batch
        assert len(received_batches) == 1
        assert len(received_batches[0]) == 3

    @pytest.mark.asyncio
    async def test_batch_pending_count(self) -> None:
        """Pending count is accurate before and after flush."""
        manager = BatchRetrievalManager(max_batch_size=5, max_wait_seconds=10.0)

        async def handler(reqs):
            return {r.request_id: None for r in reqs}

        manager.set_batch_handler(handler)

        # Before any requests
        assert manager.pending_count() == 0

        # Add one request (won't flush because batch_size not met and wait is long)
        # Use ensure_future so we don't block
        task = asyncio.ensure_future(manager.add_request("r1", "q1", "semantic", {}))
        await asyncio.sleep(0.01)
        assert manager.pending_count() == 1

        # Flush manually
        await manager.flush()
        assert manager.pending_count() == 0
        await task  # clean up


# ======================================================================
# ParallelExecutor
# ======================================================================


class TestParallelExecutor:
    """Tests for the ParallelExecutor concurrency control."""

    @pytest.mark.asyncio
    async def test_parallel_single_task(self) -> None:
        """Single task completes successfully."""
        executor = ParallelExecutor(max_concurrent=5)

        async def work():
            return "done"

        results = await executor.execute_parallel([("task_1", work, (), {})])
        assert results["task_1"] == "done"

    @pytest.mark.asyncio
    async def test_parallel_multiple_tasks(self) -> None:
        """Multiple tasks execute and return results."""
        executor = ParallelExecutor(max_concurrent=5)

        async def work(val):
            return val * 2

        tasks = [(f"task_{i}", work, (i,), {}) for i in range(5)]
        results = await executor.execute_parallel(tasks)

        for i in range(5):
            assert results[f"task_{i}"] == i * 2

    @pytest.mark.asyncio
    async def test_parallel_concurrency_limit(self) -> None:
        """Respects max_concurrent limit via semaphore."""
        executor = ParallelExecutor(max_concurrent=2, max_per_agent=2)
        max_active = 0
        lock = asyncio.Lock()

        async def work(idx):
            nonlocal max_active
            # Small sleep to create overlap
            await asyncio.sleep(0.02)
            current = executor.active_count()
            async with lock:
                if current > max_active:
                    max_active = current

        tasks = [(f"t_{i}", work, (i,), {}) for i in range(4)]
        await executor.execute_parallel(tasks)

        # active_count should never have exceeded 2
        assert max_active <= 2

    @pytest.mark.asyncio
    async def test_parallel_stats(self) -> None:
        """Execution stats are tracked correctly."""
        executor = ParallelExecutor(max_concurrent=3, max_per_agent=1)

        async def work():
            await asyncio.sleep(0.01)
            return "ok"

        async def fail():
            await asyncio.sleep(0.005)
            raise ValueError("boom")

        await executor.execute_parallel(
            [
                ("s1", work, (), {}),
                ("s2", work, (), {}),
                ("f1", fail, (), {}),
            ]
        )

        stats = executor.stats()
        assert stats["total_completed"] == 2
        assert stats["total_failed"] == 1
        assert stats["max_concurrent"] == 3
        assert stats["max_per_agent"] == 1
        assert stats["total_time_ms"] >= 0
        assert stats["active"] == 0  # all done

    @pytest.mark.asyncio
    async def test_parallel_empty_tasks(self) -> None:
        """Empty task list returns empty results."""
        executor = ParallelExecutor()
        results = await executor.execute_parallel([])
        assert results == {}


# ======================================================================
# TimeoutRecoveryManager
# ======================================================================


class TestTimeoutRecoveryManager:
    """Tests for the TimeoutRecoveryManager recovery logic."""

    @pytest.mark.asyncio
    async def test_timeout_skip_and_continue(self) -> None:
        """skip_and_continue strategy removes agent from pending."""
        mgr = TimeoutRecoveryManager(recovery_strategy="skip_and_continue")
        state: dict = {
            "pending_agents": ["agent_a", "agent_b"],
            "errors": [],
            "evidence": [{"src": "partial"}],
        }

        updated = await mgr.handle_timeout("agent_a", state, partial_result=None)
        assert "agent_a" not in updated["pending_agents"]
        assert "agent_b" in updated["pending_agents"]
        assert any("TIMEOUT_SKIPPED" in e for e in updated["errors"])

    @pytest.mark.asyncio
    async def test_timeout_history(self) -> None:
        """Timeout events are tracked in history."""
        mgr = TimeoutRecoveryManager()
        state: dict = {"pending_agents": ["a"], "errors": []}

        await mgr.handle_timeout("a", state)
        await mgr.handle_timeout("a", state)

        history = mgr.get_timeout_history()
        assert len(history) == 2
        assert history[0]["agent_name"] == "a"
        assert history[0]["has_partial_result"] is False

    @pytest.mark.asyncio
    async def test_timeout_escalation(self) -> None:
        """After 3 timeouts for same agent -> should_escalate returns True."""
        mgr = TimeoutRecoveryManager(recovery_strategy="skip_and_continue")
        state: dict = {"pending_agents": ["a"], "errors": []}

        for _ in range(3):
            await mgr.handle_timeout("a", state)

        assert mgr.should_escalate("a") is True

    @pytest.mark.asyncio
    async def test_timeout_no_escalation(self) -> None:
        """Single timeout -> no escalation."""
        mgr = TimeoutRecoveryManager()
        state: dict = {"pending_agents": ["a"], "errors": []}

        await mgr.handle_timeout("a", state)
        assert mgr.should_escalate("a") is False

    @pytest.mark.asyncio
    async def test_timeout_partial_result_merged(self) -> None:
        """Partial result dict is merged into state on skip."""
        mgr = TimeoutRecoveryManager(recovery_strategy="skip_and_continue")
        state: dict = {
            "pending_agents": ["a"],
            "errors": [],
            "evidence": [{"old": True}],
        }
        partial = {"evidence": [{"new": True}]}

        updated = await mgr.handle_timeout("a", state, partial_result=partial)
        # evidence lists should be extended
        assert len(updated["evidence"]) == 2
        assert updated["evidence"][1] == {"new": True}

    @pytest.mark.asyncio
    async def test_timeout_different_agents_no_escalation(self) -> None:
        """Timeouts for different agents do not trigger escalation."""
        mgr = TimeoutRecoveryManager(recovery_strategy="skip_and_continue")
        state: dict = {"pending_agents": ["a", "b", "c"], "errors": []}

        for name in ["a", "b", "c"]:
            await mgr.handle_timeout(name, state)

        assert mgr.should_escalate("a") is False
        assert mgr.should_escalate("b") is False
        assert mgr.should_escalate("c") is False


# ======================================================================
# ProductionOptimizer
# ======================================================================


class TestProductionOptimizer:
    """Tests for the ProductionOptimizer unified facade."""

    def test_optimizer_properties(self) -> None:
        """All properties return correct typed instances."""
        opt = ProductionOptimizer()
        assert isinstance(opt.cache, ResponseCache)
        assert isinstance(opt.batch_manager, BatchRetrievalManager)
        assert isinstance(opt.parallel_executor, ParallelExecutor)
        assert isinstance(opt.timeout_recovery, TimeoutRecoveryManager)

    def test_optimization_report(self) -> None:
        """Report includes all optimizer stats."""
        opt = ProductionOptimizer()

        # Seed some data
        opt.cache.put("tool", {"q": 1}, "value")
        opt.cache.get("tool", {"q": 1})  # hit
        opt.cache.get("tool", {"q": 2})  # miss

        report = opt.get_optimization_report()

        assert "cache" in report
        assert "batch" in report
        assert "parallel" in report
        assert "timeout_recovery" in report

        # Cache stats
        assert report["cache"]["hits"] == 1
        assert report["cache"]["misses"] == 1
        assert report["cache"]["size"] == 1

        # Batch
        assert report["batch"]["pending_requests"] == 0

        # Parallel
        assert report["parallel"]["total_completed"] == 0
        assert report["parallel"]["active"] == 0

        # Timeout
        assert report["timeout_recovery"]["strategy"] == "skip_and_continue"
        assert report["timeout_recovery"]["total_timeouts"] == 0
        assert report["timeout_recovery"]["history"] == []

    @pytest.mark.asyncio
    async def test_optimizer_cleanup(self) -> None:
        """Cleanup runs cache eviction and batch flush."""
        opt = ProductionOptimizer()

        # Seed cache with a TTL=0 entry
        opt.cache.put("t", {"q": 1}, "v", ttl_seconds=0.0)
        time.sleep(0.01)
        await opt.cleanup()

        assert opt.cache.get("t", {"q": 1}) is None
