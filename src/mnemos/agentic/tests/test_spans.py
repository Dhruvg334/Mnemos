"""Tests for the Observability Spans system.

Covers Span, SpanExporter, SpanContext, TracingManager.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from mnemos.agentic.runtime.spans import (
    Span,
    SpanContext,
    SpanEvent,
    SpanExporter,
    SpanStatus,
    TracingManager,
)

# =====================================================================
# Test: SpanStatus enum
# =====================================================================


class TestSpanStatus:
    def test_all_statuses(self):
        statuses = [s.value for s in SpanStatus]
        assert sorted(statuses) == ["cancelled", "error", "ok", "timeout"]


# =====================================================================
# Test: SpanEvent
# =====================================================================


class TestSpanEvent:
    def test_creation(self):
        event = SpanEvent(name="evidence_found", attributes={"count": 5})
        assert event.name == "evidence_found"
        assert event.attributes["count"] == 5
        assert event.timestamp > 0

    def test_defaults(self):
        event = SpanEvent(name="test")
        assert event.attributes == {}


# =====================================================================
# Test: Span
# =====================================================================


class TestSpan:
    def test_creation(self):
        span = Span(name="agent.rca", operation="rca_analysis")
        assert span.span_id.startswith("spn_")
        assert span.is_recording is True
        assert span.duration_ms is None

    def test_add_event(self):
        span = Span(name="test")
        event = span.add_event("milestone", {"step": 1})
        assert len(span.events) == 1
        assert event.name == "milestone"

    def test_set_attribute(self):
        span = Span(name="test")
        span.set_attribute("agent", "rca_agent")
        assert span.attributes["agent"] == "rca_agent"

    def test_finish_ok(self):
        span = Span(name="test")
        span.finish(status=SpanStatus.OK)
        assert span.is_recording is False
        assert span.status == SpanStatus.OK
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_finish_error(self):
        span = Span(name="test")
        span.finish(status=SpanStatus.ERROR, message="DB timeout")
        assert span.status == SpanStatus.ERROR
        assert span.status_message == "DB timeout"

    def test_to_export_dict(self):
        span = Span(name="test", trace_id="t1", operation="op1")
        span.set_attribute("key", "value")
        span.add_event("event1")
        span.finish()

        d = span.to_export_dict()
        assert d["name"] == "test"
        assert d["trace_id"] == "t1"
        assert d["status"] == "ok"
        assert d["duration_ms"] >= 0
        assert len(d["events"]) == 1


# =====================================================================
# Test: SpanExporter
# =====================================================================


class TestSpanExporter:
    def test_callback_export(self):
        exported = []
        exporter = SpanExporter()
        exporter.add_callback(lambda s: exported.append(s))

        span = Span(name="test")
        span.finish()
        exporter.export(span)

        assert len(exported) == 1
        assert exported[0].name == "test"

    def test_file_export(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        try:
            exporter = SpanExporter()
            exporter.set_file_output(path)

            span = Span(name="test", trace_id="t1")
            span.finish()
            exporter.export(span)

            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["name"] == "test"
            assert data["trace_id"] == "t1"
        finally:
            os.unlink(path)

    def test_exported_count(self):
        exporter = SpanExporter()
        span = Span(name="test")
        span.finish()
        exporter.export(span)
        assert exporter.exported_count == 1

    def test_callback_exception_swallowed(self):
        def bad_callback(span):
            raise RuntimeError("oops")

        exporter = SpanExporter()
        exporter.add_callback(bad_callback)

        span = Span(name="test")
        span.finish()
        exporter.export(span)
        assert exporter.exported_count == 1


# =====================================================================
# Test: SpanContext
# =====================================================================


class TestSpanContext:
    def test_context_manager(self):
        ctx = SpanContext(trace_id="inv_001")
        with ctx.start_span("agent.rca") as span:
            assert span.name == "agent.rca"
            assert span.trace_id == "inv_001"
            assert span.is_recording is True
        assert span.is_recording is False
        assert span.status == SpanStatus.OK

    def test_context_error_handling(self):
        ctx = SpanContext(trace_id="inv_001")
        with pytest.raises(RuntimeError):
            with ctx.start_span("agent.rca") as span:
                raise RuntimeError("test error")
        assert span.status == SpanStatus.ERROR
        assert "test error" in (span.status_message or "")

    def test_context_with_exporter(self):
        exported = []
        exporter = SpanExporter()
        exporter.add_callback(lambda s: exported.append(s))

        ctx = SpanContext(trace_id="inv_001", exporter=exporter)
        with ctx.start_span("test") as span:
            span.set_attribute("key", "value")

        assert len(exported) == 1
        assert exported[0].attributes["key"] == "value"


# =====================================================================
# Test: TracingManager
# =====================================================================


class TestTracingManager:
    def test_basic_span(self):
        manager = TracingManager(trace_id="inv_001")
        with manager.start_span("agent.rca") as span:
            span.set_attribute("agent", "rca_agent")
            span.add_event("started")

        assert manager.get_completed_spans().__len__() == 1

    def test_nested_spans(self):
        manager = TracingManager(trace_id="inv_001")
        with manager.start_span("outer") as outer:
            with manager.start_span("inner") as inner:
                pass

        assert outer.parent_span_id is None
        assert inner.parent_span_id == outer.span_id

    def test_active_span_tracking(self):
        manager = TracingManager(trace_id="inv_001")
        assert manager.get_active_span() is None

        with manager.start_span("span1") as s1:
            assert manager.get_active_span() is s1
            with manager.start_span("span2") as s2:
                assert manager.get_active_span() is s2
            assert manager.get_active_span() is s1
        assert manager.get_active_span() is None

    def test_summary(self):
        manager = TracingManager(trace_id="inv_001")
        with manager.start_span("op1") as s1:
            s1.set_attribute("key", "val")
        with manager.start_span("op2") as s2:
            s2.finish(status=SpanStatus.ERROR, message="fail")

        s = manager.summary()
        assert s["trace_id"] == "inv_001"
        assert s["total_spans"] == 2
        assert s["completed_spans"] == 2
        assert s["error_spans"] == 1
        assert s["total_duration_ms"] >= 0

    def test_export_all(self):
        manager = TracingManager(trace_id="inv_001")
        with manager.start_span("op1"):
            pass
        with manager.start_span("op2"):
            pass

        exported = manager.export_all()
        assert len(exported) == 2
        assert all("span_id" in e for e in exported)

    def test_error_span_tracked(self):
        manager = TracingManager(trace_id="inv_001")
        with pytest.raises(ValueError):
            with manager.start_span("failing_op") as span:
                raise ValueError("test failure")

        assert span.status == SpanStatus.ERROR
        s = manager.summary()
        assert s["error_spans"] == 1

    def test_exporter_wired(self):
        exported = []
        exporter = SpanExporter()
        exporter.add_callback(lambda s: exported.append(s))
        manager = TracingManager(trace_id="inv_001", exporter=exporter)

        with manager.start_span("op1"):
            pass

        assert len(exported) == 1
        assert manager.summary()["exported_count"] == 1

    def test_get_spans(self):
        manager = TracingManager(trace_id="inv_001")
        with manager.start_span("op1"):
            pass
        with manager.start_span("op2"):
            pass

        spans = manager.get_spans()
        assert len(spans) == 2
