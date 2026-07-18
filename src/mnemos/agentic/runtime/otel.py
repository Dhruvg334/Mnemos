"""OpenTelemetry tracing integration (P0 #17).

Provides real OTLP-compatible trace spans for every stage of the
investigation pipeline.  When an OTLP endpoint is configured via
``OTEL_EXPORTER_OTLP_ENDPOINT`` the spans are exported to the external
backend (Jaeger, Grafana Tempo, Honeycomb, etc.).

When no endpoint is configured the tracer falls back to a no-op tracer
so the pipeline always runs without requiring observability infrastructure.

Span coverage (P0 #17):
- api_request
- query_classification
- entity_resolution
- retrieval_planning
- metadata_retrieval
- lexical_retrieval
- vector_retrieval
- graph_traversal
- candidate_fusion
- reranking
- specialist_agent (one span per agent)
- reflection
- evidence_verification
- answer_composition
- approval_gate
- tool_call (one span per tool)
- persistence

Usage::

    from mnemos.agentic.runtime.otel import get_tracer, record_span_attrs

    tracer = get_tracer()
    with tracer.start_as_current_span("vector_retrieval") as span:
        record_span_attrs(span, {
            "retrieval.candidate_count": 42,
            "retrieval.model": "text-embedding-3-small",
        })
        results = await retrieve(...)
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import OpenTelemetry; fall back to no-ops if not installed
# ---------------------------------------------------------------------------

_OTEL_AVAILABLE = False
_TRACER: Any = None

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    _OTEL_AVAILABLE = True
except ImportError:
    logger.debug("opentelemetry-sdk not installed; using no-op tracer")


def _build_tracer() -> Any:
    """Build and return a configured OpenTelemetry tracer.

    If ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set, exports to that endpoint
    via OTLP/HTTP.  Otherwise falls back to ConsoleSpanExporter (stdout)
    when ``OTEL_TRACES_CONSOLE=true``, or a no-op tracer.
    """
    if not _OTEL_AVAILABLE:
        return _NoOpTracer()

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    resource = Resource(attributes={
        SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "mnemos-agentic"),
        "service.version": os.getenv("APP_VERSION", "0.1.0"),
        "deployment.environment": os.getenv("APP_ENV", "development"),
    })

    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                headers={
                    k: v
                    for k, v in [
                        ("Authorization", os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")),
                    ]
                    if v
                },
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(
                "OpenTelemetry OTLP exporter configured: %s", otlp_endpoint
            )
        except ImportError:
            logger.warning(
                "opentelemetry-exporter-otlp-proto-http not installed; "
                "OTLP export disabled.  Install with: "
                "pip install opentelemetry-exporter-otlp-proto-http"
            )
    elif os.getenv("OTEL_TRACES_CONSOLE", "").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("OpenTelemetry console exporter enabled")

    trace.set_tracer_provider(provider)
    return trace.get_tracer("mnemos.agentic", os.getenv("APP_VERSION", "0.1.0"))


def get_tracer() -> Any:
    """Return the singleton OpenTelemetry tracer (or no-op fallback)."""
    global _TRACER
    if _TRACER is None:
        _TRACER = _build_tracer()
    return _TRACER


def record_span_attrs(span: Any, attrs: dict[str, Any]) -> None:
    """Set attributes on a span, safely handling non-OTel spans."""
    try:
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(key, value)
    except Exception:
        pass


def record_span_event(span: Any, name: str, attrs: dict[str, Any] | None = None) -> None:
    """Add an event to a span, safely handling non-OTel spans."""
    try:
        span.add_event(name, attributes=attrs or {})
    except Exception:
        pass


def set_span_error(span: Any, exc: BaseException) -> None:
    """Record an exception on a span without leaking internals."""
    try:
        if _OTEL_AVAILABLE:
            from opentelemetry.trace import Status, StatusCode
            span.set_status(Status(StatusCode.ERROR))
            # Record only the error type, not the full message (P0 #14)
            span.set_attribute("error.type", type(exc).__name__)
        else:
            span.status = "error"
    except Exception:
        pass


# ---------------------------------------------------------------------------
# No-op tracer for when opentelemetry-sdk is not installed
# ---------------------------------------------------------------------------


class _NoOpSpan:
    """Minimal no-op span that accepts all attribute/event calls."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, **kwargs: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoOpTracer:
    """Minimal no-op tracer returned when opentelemetry-sdk is unavailable."""

    @contextmanager
    def start_as_current_span(
        self, name: str, **kwargs: Any
    ) -> Generator[_NoOpSpan, None, None]:
        yield _NoOpSpan()

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()


# ---------------------------------------------------------------------------
# Span name constants
# ---------------------------------------------------------------------------


class SpanName:
    """Standard span names for the investigation pipeline (P0 #17)."""

    API_REQUEST = "mnemos.api.request"
    QUERY_CLASSIFICATION = "mnemos.pipeline.query_classification"
    ENTITY_RESOLUTION = "mnemos.pipeline.entity_resolution"
    RETRIEVAL_PLANNING = "mnemos.pipeline.retrieval_planning"
    METADATA_RETRIEVAL = "mnemos.pipeline.metadata_retrieval"
    LEXICAL_RETRIEVAL = "mnemos.pipeline.lexical_retrieval"
    VECTOR_RETRIEVAL = "mnemos.pipeline.vector_retrieval"
    GRAPH_TRAVERSAL = "mnemos.pipeline.graph_traversal"
    CANDIDATE_FUSION = "mnemos.pipeline.candidate_fusion"
    RERANKING = "mnemos.pipeline.reranking"
    SPECIALIST_AGENT = "mnemos.agent"          # suffix with agent name
    REFLECTION = "mnemos.pipeline.reflection"
    EVIDENCE_VERIFICATION = "mnemos.pipeline.evidence_verification"
    ANSWER_COMPOSITION = "mnemos.pipeline.answer_composition"
    APPROVAL_GATE = "mnemos.pipeline.approval_gate"
    TOOL_CALL = "mnemos.tool"                  # suffix with tool name
    PERSISTENCE = "mnemos.persistence"
