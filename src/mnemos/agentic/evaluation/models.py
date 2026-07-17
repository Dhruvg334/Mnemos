from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvalPipelineType(StrEnum):
    """Pipeline variant under evaluation."""

    MNEMOS_GRAPH_RAG = "mnemos_graph_rag"
    BASELINE_VECTOR_RAG = "baseline_vector_rag"


class EvalSample(BaseModel):
    """A single evaluation sample with ground truth annotations."""

    query: str
    ground_truth: str | None = None
    expected_intent: str | None = None
    expected_entities: list[str] = Field(
        default_factory=list,
        description="Expected canonical entity IDs that should be resolved.",
    )
    expected_document_ids: list[str] = Field(
        default_factory=list,
        description="Expected source document IDs that should be retrieved.",
    )
    expected_citation_ids: list[str] = Field(
        default_factory=list,
        description="Expected citation IDs in the final output.",
    )
    expected_root_cause: str | None = None
    expected_compliance_status: str | None = None
    ground_truth_available: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalDataset(BaseModel):
    """A named collection of evaluation samples."""

    name: str
    description: str
    samples: list[EvalSample]
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricResult(BaseModel):
    """Result of a single metric computation on one sample."""

    name: str
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, description="Relative importance for aggregation.")
    reasoning: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SampleResult(BaseModel):
    """Per-sample evaluation output with all metric values and extracted data."""

    sample_index: int
    query: str
    answer: str
    latency_ms: float
    metrics: list[MetricResult] = Field(default_factory=list)
    retrieved_contexts: list[str] = Field(default_factory=list)
    retrieved_document_ids: list[str] = Field(default_factory=list)
    resolved_entities: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    claim_count: int = 0
    grounded_claim_count: int = 0
    hallucination_detected: bool = False
    phase: str | None = None
    aborted: bool = False
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class BenchmarkReport(BaseModel):
    """Full benchmark report with summary metrics, per-sample results, and timing."""

    benchmark_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    benchmark_name: str
    pipeline_type: EvalPipelineType
    dataset_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary_metrics: dict[str, float] = Field(default_factory=dict)
    sample_results: list[SampleResult] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    avg_latency_ms: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComparisonReport(BaseModel):
    """Lift/drop comparison between two benchmark reports."""

    comparison_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    name: str
    report_primary: BenchmarkReport
    report_secondary: BenchmarkReport
    deltas: dict[str, float] = Field(
        default_factory=dict,
        description="Percentage lift (positive) or drop (negative) for each metric.",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvaluationRun(BaseModel):
    """A complete evaluation run containing one or more benchmark reports."""

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    dataset_name: str
    benchmarks: list[BenchmarkReport] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
