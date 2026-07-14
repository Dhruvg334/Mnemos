from typing import List, Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_admin
from mnemos.core.db import get_db
from mnemos.schemas.common import Envelope, Meta
from mnemos.agentic.evaluation.models import (
    EvalDataset,
    BenchmarkReport,
    ComparisonReport,
    EvalPipelineType
)
from mnemos.agentic.evaluation.runner import BenchmarkRunner
from mnemos.agentic.evaluation.reporter import EvaluationReporter
from mnemos.agentic.utils.logging import StructuredLogger

router = APIRouter(prefix="/evaluation", tags=["ai-evaluation"])
logger = StructuredLogger("evaluation_api")

@router.post("/benchmark", response_model=Envelope[BenchmarkReport])
async def trigger_benchmark(
    dataset: EvalDataset,
    background_tasks: BackgroundTasks,
    pipeline_type: EvalPipelineType = EvalPipelineType.MNEMOS_GRAPH_RAG,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_principal)
):
    """
    Triggers a performance benchmark for a given dataset and pipeline type.
    Administrator access required.
    """
    require_admin(principal)

    runner = BenchmarkRunner(db)

    # Run benchmark asynchronously
    # In a production environment, this would be a long-running job with status tracking
    report = await runner.run_benchmark(dataset, pipeline_type=pipeline_type)

    return Envelope(
        data=report,
        meta=Meta(request_id="eval-task")
    )

@router.post("/compare", response_model=Envelope[ComparisonReport])
async def compare_pipelines(
    dataset: EvalDataset,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_principal)
):
    """
    Performs a comparative evaluation between Mnemos GraphRAG and a Baseline Vector RAG.
    Shows the performance 'lift' provided by the specialized architecture.
    """
    require_admin(principal)

    runner = BenchmarkRunner(db)
    reporter = EvaluationReporter()

    # 1. Run Mnemos Pipeline
    report_mnemos = await runner.run_benchmark(
        dataset,
        pipeline_type=EvalPipelineType.MNEMOS_GRAPH_RAG,
        benchmark_name="Mnemos_GraphRAG_Test"
    )

    # 2. Run Baseline Pipeline
    report_baseline = await runner.run_benchmark(
        dataset,
        pipeline_type=EvalPipelineType.BASELINE_VECTOR_RAG,
        benchmark_name="Baseline_VectorRAG_Test"
    )

    # 3. Generate Comparison
    comparison = reporter.compare_benchmarks(report_mnemos, report_baseline)

    return Envelope(
        data=comparison,
        meta=Meta(request_id="comp-task")
    )
