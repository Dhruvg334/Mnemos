"""Observability Spans for the Mnemos agentic runtime.

Provides structured, OpenTelemetry-compatible tracing spans:
- Span: individual operation with start/end, attributes, status
- SpanContext: propagates trace/span IDs through the call chain
- SpanExporter: exports spans to stdout, files, or callbacks
- TracingManager: manages span lifecycle and context propagation

Zero business logic — only reusable observability architecture.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SpanStatus(StrEnum):
    """Span completion status."""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class SpanEvent(BaseModel):
    """An event within a span (e.g., log message, milestone)."""
    name: str
    timestamp: float = Field(default_factory=time.time)
    attributes: dict[str, Any] = Field(default_factory=dict)


class Span(BaseModel):
    """A single tracing span representing an operation."""
    span_id: str = Field(default_factory=lambda: f"spn_{uuid.uuid4().hex[:12]}")
    trace_id: str = ""
    parent_span_id: str | None = None
    name: str = ""
    operation: str = ""
    start_time: float = Field(default_factory=time.time)
    end_time: float | None = None
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[SpanEvent] = Field(default_factory=list)
    status_message: str | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    @property
    def is_recording(self) -> bool:
        return self.end_time is None

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> SpanEvent:
        event = SpanEvent(name=name, attributes=attributes or {})
        self.events.append(event)
        return event

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def finish(self, status: SpanStatus = SpanStatus.OK, message: str | None = None) -> None:
        self.end_time = time.time()
        self.status = status
        self.status_message = message

    def to_export_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": [e.model_dump() for e in self.events],
        }


class SpanExporter:
    """Exports completed spans to various backends.

    Supports:
    - stdout: prints span JSON to stdout
    - file: appends span JSON to a file
    - callback: calls a user-provided function with each span
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[[Span], None]] = []
        self._file_path: str | None = None
        self._exported_count = 0

    def add_callback(self, callback: Callable[[Span], None]) -> None:
        self._callbacks.append(callback)

    def set_file_output(self, file_path: str) -> None:
        self._file_path = file_path

    def export(self, span: Span) -> None:
        self._exported_count += 1

        for cb in self._callbacks:
            try:
                cb(span)
            except Exception:
                logger.warning("Span export callback failed", exc_info=True)

        if self._file_path:
            try:
                with open(self._file_path, "a") as f:
                    f.write(json.dumps(span.to_export_dict(), default=str) + "\n")
            except Exception:
                logger.warning("Span file export failed for %s", self._file_path, exc_info=True)

    @property
    def exported_count(self) -> int:
        return self._exported_count


class SpanContext:
    """Context for propagating trace/span IDs through the call chain.

    Usage:
        ctx = SpanContext(trace_id="inv_001")
        with ctx.start_span("agent.rca") as span:
            span.set_attribute("agent", "rca_agent")
            # ... do work ...
            span.add_event("evidence_found", {"count": 5})
    """

    def __init__(
        self,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        exporter: SpanExporter | None = None,
    ) -> None:
        self.trace_id = trace_id or f"trace_{uuid.uuid4().hex[:10]}"
        self.parent_span_id = parent_span_id
        self.exporter = exporter

    def start_span(
        self,
        name: str,
        operation: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> _SpanContextManager:
        span = Span(
            trace_id=self.trace_id,
            parent_span_id=self.parent_span_id,
            name=name,
            operation=operation,
            attributes=attributes or {},
        )
        return _SpanContextManager(span, self.exporter)


class _SpanContextManager:
    """Context manager for a span (with-statement support)."""

    def __init__(
        self,
        span: Span,
        exporter: SpanExporter | None = None,
        active_stack: list[Span] | None = None,
    ) -> None:
        self.span = span
        self.exporter = exporter
        self._active_stack = active_stack

    def __enter__(self) -> Span:
        return self.span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.span.is_recording:
            if exc_type is not None:
                self.span.finish(
                    status=SpanStatus.ERROR,
                    message=str(exc_val) if exc_val else "Unknown error",
                )
            else:
                self.span.finish(status=SpanStatus.OK)

        if self._active_stack and self.span in self._active_stack:
            self._active_stack.remove(self.span)

        if self.exporter:
            self.exporter.export(self.span)


class TracingManager:
    """Manages the lifecycle of spans for an investigation.

    Provides:
    - Span creation with automatic context propagation
    - Active span tracking (for nesting)
    - Bulk export of all spans
    - Summary statistics
    """

    def __init__(
        self,
        trace_id: str | None = None,
        exporter: SpanExporter | None = None,
    ) -> None:
        self._trace_id = trace_id or f"trace_{uuid.uuid4().hex[:10]}"
        self._exporter = exporter or SpanExporter()
        self._spans: list[Span] = []
        self._active_stack: list[Span] = []

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def start_span(
        self,
        name: str,
        operation: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> _SpanContextManager:
        parent_id = self._active_stack[-1].span_id if self._active_stack else None

        span = Span(
            trace_id=self._trace_id,
            parent_span_id=parent_id,
            name=name,
            operation=operation,
            attributes=attributes or {},
        )

        self._spans.append(span)
        self._active_stack.append(span)

        return _SpanContextManager(span, self._exporter, self._active_stack)

    def get_spans(self) -> list[Span]:
        return list(self._spans)

    def get_completed_spans(self) -> list[Span]:
        return [s for s in self._spans if not s.is_recording]

    def get_active_span(self) -> Span | None:
        return self._active_stack[-1] if self._active_stack else None

    def summary(self) -> dict[str, Any]:
        completed = self.get_completed_spans()
        durations = [s.duration_ms for s in completed if s.duration_ms is not None]
        errors = [s for s in completed if s.status == SpanStatus.ERROR]

        return {
            "trace_id": self._trace_id,
            "total_spans": len(self._spans),
            "completed_spans": len(completed),
            "active_spans": len(self._active_stack),
            "error_spans": len(errors),
            "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "total_duration_ms": round(sum(durations), 2) if durations else 0,
            "exported_count": self._exporter.exported_count,
        }

    def export_all(self) -> list[dict[str, Any]]:
        """Export all completed spans as dicts."""
        return [s.to_export_dict() for s in self.get_completed_spans()]
