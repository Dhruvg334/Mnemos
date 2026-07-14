from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class EvalPipelineType(StrEnum):
    MNEMOS_GRAPH_RAG = "mnemos_graph_rag"
    BASELINE_VECTOR_RAG = "baseline_vector_rag"

class EvalSample(BaseModel):
    query: str
    ground_truth: Optional[str] = None
    expected_entities: List[str] = Field(default_factory=list, description="Expected canonical asset IDs.")
    expected_document_ids: List[str] = Field(default_factory=list, description="Document IDs that must be cited/retrieved.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EvalDataset(BaseModel):
    name: str
    description: str
    samples: List[EvalSample]

class MetricResult(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SampleResult(BaseModel):
    sample: EvalSample
    answer: str
    retrieved_contexts: List[str]
    retrieved_document_ids: List[str] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    resolved_entities: List[str] = Field(default_factory=list)
    metrics: List[MetricResult]
    latency_ms: float
    hallucination_detected: bool
    grounded_answer_rate: float

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
    deltas: Dict[str, float] # Percentage lift for each metric
    timestamp: datetime = Field(default_factory=datetime.utcnow)
