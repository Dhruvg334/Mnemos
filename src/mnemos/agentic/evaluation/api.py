from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mnemos.agentic.evaluation.models import (
    BenchmarkReport,
    ComparisonReport,
    EvalDataset,
    EvalPipelineType,
)
from mnemos.agentic.evaluation.reporter import EvalReporter
from mnemos.agentic.evaluation.runner import EvalRunner
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("evaluation_api")

router = APIRouter(prefix="/evaluation", tags=["ai-evaluation"])

# ---------------------------------------------------------------------------
# In-memory store for reports (production would use a database).
# ---------------------------------------------------------------------------
_report_store: dict[str, BenchmarkReport] = {}
_comparison_store: dict[str, ComparisonReport] = {}

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RunBenchmarkRequest(BaseModel):
    """Request body for POST /evaluation/run."""

    dataset: EvalDataset
    pipeline_type: EvalPipelineType = EvalPipelineType.MNEMOS_GRAPH_RAG
    benchmark_name: str | None = None
    timeout_seconds: float = Field(default=300.0, gt=0)
    max_concurrency: int = Field(default=10, ge=1, le=100)


class RunBenchmarkResponse(BaseModel):
    """Response body for POST /evaluation/run."""

    report_id: str
    report: BenchmarkReport
    markdown: str


class CompareRequest(BaseModel):
    """Request body for POST /evaluation/compare."""

    primary_dataset: EvalDataset
    secondary_dataset: EvalDataset | None = None
    primary_pipeline: EvalPipelineType = EvalPipelineType.MNEMOS_GRAPH_RAG
    secondary_pipeline: EvalPipelineType = EvalPipelineType.BASELINE_VECTOR_RAG
    benchmark_name_primary: str | None = None
    benchmark_name_secondary: str | None = None
    timeout_seconds: float = Field(default=300.0, gt=0)
    max_concurrency: int = Field(default=10, ge=1, le=100)


class CompareResponse(BaseModel):
    """Response body for POST /evaluation/compare."""

    comparison_id: str
    comparison: ComparisonReport
    markdown: str


class ReportResponse(BaseModel):
    """Response body for GET /evaluation/reports/{report_id}."""

    report_id: str
    report: BenchmarkReport
    markdown: str
    json: str


class ComparisonReportResponse(BaseModel):
    """Response body for GET /evaluation/comparisons/{comparison_id}."""

    comparison_id: str
    comparison: ComparisonReport
    markdown: str
    json: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    response_model=RunBenchmarkResponse,
    status_code=200,
    summary="Run a benchmark evaluation",
)
async def run_benchmark(
    request: RunBenchmarkRequest,
) -> RunBenchmarkResponse:
    """Execute a full benchmark evaluation against a workflow.

    The caller must supply a ``workflow_fn`` at application startup (or via
    dependency injection).  This endpoint uses the default registered
    workflow function.

    For demonstration purposes this endpoint returns a skeleton runner that
    expects the caller to configure ``_workflow_fn`` before use.
    """
    if _workflow_fn is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "No workflow function registered. "
                "Call `register_workflow_fn()` at application startup."
            ),
        )

    runner = EvalRunner(
        workflow_fn=_workflow_fn,
        pipeline_type=request.pipeline_type,
        timeout_seconds=request.timeout_seconds,
        max_concurrency=request.max_concurrency,
    )

    try:
        report = await runner.run_benchmark(
            dataset=request.dataset,
            benchmark_name=request.benchmark_name,
        )
    except Exception as exc:
        logger.error(f"Benchmark run failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    report_id = report.benchmark_id
    _report_store[report_id] = report
    markdown = EvalReporter.to_markdown(report)

    return RunBenchmarkResponse(
        report_id=report_id,
        report=report,
        markdown=markdown,
    )


@router.post(
    "/compare",
    response_model=CompareResponse,
    status_code=200,
    summary="Compare two pipeline configurations",
)
async def compare_pipelines(
    request: CompareRequest,
) -> CompareResponse:
    """Run two pipelines against the same dataset and produce a comparison.

    If ``secondary_dataset`` is ``None`` the primary dataset is reused for
    the secondary pipeline.
    """
    if _workflow_fn is None:
        raise HTTPException(
            status_code=503,
            detail="No workflow function registered.",
        )

    secondary_dataset = request.secondary_dataset or request.dataset

    runner_primary = EvalRunner(
        workflow_fn=_workflow_fn,
        pipeline_type=request.primary_pipeline,
        timeout_seconds=request.timeout_seconds,
        max_concurrency=request.max_concurrency,
    )

    report_primary = await runner_primary.run_benchmark(
        dataset=request.dataset,
        benchmark_name=request.benchmark_name_primary or "primary",
    )

    runner_secondary = EvalRunner(
        workflow_fn=_workflow_fn,
        pipeline_type=request.secondary_pipeline,
        timeout_seconds=request.timeout_seconds,
        max_concurrency=request.max_concurrency,
    )

    report_secondary = await runner_secondary.run_benchmark(
        dataset=secondary_dataset,
        benchmark_name=request.benchmark_name_secondary or "secondary",
    )

    comparison = EvalReporter.compare(report_primary, report_secondary)
    _report_store[report_primary.benchmark_id] = report_primary
    _report_store[report_secondary.benchmark_id] = report_secondary
    _comparison_store[comparison.comparison_id] = comparison

    markdown = EvalReporter.comparison_to_markdown(comparison)

    return CompareResponse(
        comparison_id=comparison.comparison_id,
        comparison=comparison,
        markdown=markdown,
    )


@router.get(
    "/reports/{report_id}",
    response_model=ReportResponse,
    summary="Retrieve a stored benchmark report",
)
async def get_report(report_id: str) -> ReportResponse:
    """Fetch a previously generated benchmark report by its ID."""
    report = _report_store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")

    return ReportResponse(
        report_id=report_id,
        report=report,
        markdown=EvalReporter.to_markdown(report),
        json=EvalReporter.to_json(report),
    )


@router.get(
    "/comparisons/{comparison_id}",
    response_model=ComparisonReportResponse,
    summary="Retrieve a stored comparison report",
)
async def get_comparison(comparison_id: str) -> ComparisonReportResponse:
    """Fetch a previously generated comparison report by its ID."""
    comparison = _comparison_store.get(comparison_id)
    if comparison is None:
        raise HTTPException(
            status_code=404,
            detail=f"Comparison '{comparison_id}' not found.",
        )

    return ComparisonReportResponse(
        comparison_id=comparison_id,
        comparison=comparison,
        markdown=EvalReporter.comparison_to_markdown(comparison),
        json=EvalReporter.to_json(comparison),
    )


# ---------------------------------------------------------------------------
# Workflow function registry
# ---------------------------------------------------------------------------

_workflow_fn: Any = None


def register_workflow_fn(
    fn: Any,
) -> None:
    """Register the async workflow function used by evaluation endpoints.

    Must be called once at application startup before any evaluation
    endpoint is invoked.
    """
    global _workflow_fn
    _workflow_fn = fn
    logger.info("Workflow function registered for evaluation API.")
