from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, List
from pydantic import BaseModel, Field, ConfigDict

class EvalPipelineType(StrEnum):
    MNEMOS_GRAPH_RAG = "mnemos_graph_rag"
    BASELINE_VECTOR_RAG = "baseline_vector_rag"

class EvalSample(BaseModel):
    query: str
    ground_truth: str | None = None
    expected_entities: List[str] = Field(default_factory=list, description="Expected canonical asset IDs")
    expected_document_ids: List[str] = Field(default_factory=list, description="Expected source document IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EvalDataset(BaseModel):
    name: str
    description: str
    samples: List[EvalSample]

class MetricResult(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SampleResult(BaseModel):
    sample: EvalSample
    answer: str
    retrieved_contexts: List[str]
    retrieved_document_ids: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    resolved_entities: List[str] = Field(default_factory=list)
    metrics: List[MetricResult] = Field(default_factory=list)
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
    summary_metrics: Dict[str, float]
    sample_results: List[SampleResult]
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ComparisonReport(BaseModel):
    comparison_id: str
    report_mnemos: BenchmarkReport
    report_baseline: BenchmarkReport
    deltas: Dict[str, float] # Percentage lift/drop for each metric
    timestamp: datetime = Field(default_factory=datetime.utcnow)
