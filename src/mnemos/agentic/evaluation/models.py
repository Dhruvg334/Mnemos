from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvalPipelineType(StrEnum):
    MNEMOS_GRAPH_RAG = "mnemos_graph_rag"
    BASELINE_VECTOR_RAG = "baseline_vector_rag"

class EvalSample(BaseModel):
    query: str
    ground_truth: str | None = None
    expected_entities: list[str] = Field(default_factory=list, description="Expected canonical asset IDs")
    expected_document_ids: list[str] = Field(default_factory=list, description="Expected source document IDs")
    metadata: dict[str, Any] = Field(default_factory=dict)

class EvalDataset(BaseModel):
    name: str
    description: str
    samples: list[EvalSample]

class MetricResult(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class SampleResult(BaseModel):
    sample: EvalSample
    answer: str
    retrieved_contexts: list[str]
    retrieved_document_ids: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    resolved_entities: list[str] = Field(default_factory=list)
    metrics: list[MetricResult] = Field(default_factory=list)
    latency_ms: float
    hallucination_detected: bool
    grounded_answer_rate: float

    model_config = ConfigDict(from_attributes=True)

class BenchmarkReport(BaseModel):
    benchmark_id: str
    benchmark_name: str
    pipeline_type: EvalPipelineType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dataset_name: str
    summary_metrics: dict[str, float]
    sample_results: list[SampleResult]
    metadata: dict[str, Any] = Field(default_factory=dict)

class ComparisonReport(BaseModel):
    comparison_id: str
    report_mnemos: BenchmarkReport
    report_baseline: BenchmarkReport
    deltas: dict[str, float] # Percentage lift/drop for each metric
    timestamp: datetime = Field(default_factory=datetime.utcnow)
