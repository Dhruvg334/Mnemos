from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from mnemos.agentic.evaluation.evaluator import InvestigationEvaluator
from mnemos.agentic.evaluation.metrics import MetricAggregator
from mnemos.agentic.evaluation.models import (
    BenchmarkReport,
    EvalDataset,
    EvalPipelineType,
    EvalSample,
    MetricResult,
    SampleResult,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("eval_runner")

WorkflowFn = Callable[[str, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]


def _deterministic_id(*parts: str) -> str:
    combined = "|".join(str(p) for p in parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _deterministic_timestamp(*parts: str) -> float:
    combined = "|".join(str(p) for p in parts)
    h = hashlib.sha256(combined.encode()).hexdigest()[:8]
    return int(h, 16) / 16_777_216


class EvalRunner:
    """Execute an ``EvalDataset`` through a workflow function and evaluate results.

    Parameters
    ----------
    workflow_fn:
        An async callable ``(query, context) -> InvestigationState`` that
        runs the full investigation pipeline and returns the final state dict.
    pipeline_type:
        Identifier for the pipeline variant being benchmarked.
    evaluator:
        Optional pre-configured ``InvestigationEvaluator``.  A new instance is
        created when omitted.
    timeout_seconds:
        Maximum wall-clock time allowed per sample.  Samples that exceed this
        limit are recorded as failures.
    max_concurrency:
        Upper bound on the number of concurrent workflow invocations.
    """

    def __init__(
        self,
        workflow_fn: WorkflowFn,
        pipeline_type: EvalPipelineType = EvalPipelineType.MNEMOS_GRAPH_RAG,
        evaluator: InvestigationEvaluator | None = None,
        timeout_seconds: float = 300.0,
        max_concurrency: int = 10,
    ) -> None:
        self.workflow_fn = workflow_fn
        self.pipeline_type = pipeline_type
        self.evaluator = evaluator or InvestigationEvaluator()
        self.timeout_seconds = timeout_seconds
        self.max_concurrency = max_concurrency

    async def run_benchmark(
        self,
        dataset: EvalDataset,
        benchmark_name: str | None = None,
    ) -> BenchmarkReport:
        """Run every sample in *dataset* through the workflow and evaluate.

        Returns a ``BenchmarkReport`` containing per-sample results and
        summary statistics.
        """
        run_start = time.perf_counter()
        sem = asyncio.Semaphore(self.max_concurrency)

        async def _guarded(idx: int, sample: EvalSample) -> SampleResult:
            async with sem:
                return await self._run_one(idx, sample)

        tasks = [
            _guarded(idx, sample) for idx, sample in enumerate(dataset.samples)
        ]
        sample_results = await asyncio.gather(*tasks, return_exceptions=False)

        total_duration_ms = (time.perf_counter() - run_start) * 1000

        all_metrics: list[MetricResult] = []
        for sr in sample_results:
            all_metrics.extend(sr.metrics)

        summary = MetricAggregator.compute_summary(all_metrics)

        avg_latency = (
            sum(sr.latency_ms for sr in sample_results) / len(sample_results)
            if sample_results
            else 0.0
        )
        success_count = sum(1 for sr in sample_results if sr.error is None)
        failure_count = len(sample_results) - success_count

        summary["avg_latency_ms"] = avg_latency
        summary["total_samples"] = float(len(sample_results))
        summary["success_count"] = float(success_count)
        summary["failure_count"] = float(failure_count)

        report = BenchmarkReport(
            benchmark_id=_deterministic_id(dataset.name, self.pipeline_type.value),
            benchmark_name=benchmark_name or f"{dataset.name}_{self.pipeline_type.value}",
            pipeline_type=self.pipeline_type,
            dataset_name=dataset.name,
            timestamp=datetime.fromtimestamp(
                _deterministic_timestamp(dataset.name, self.pipeline_type.value),
                tz=UTC,
            ),
            summary_metrics=summary,
            sample_results=list(sample_results),
            total_duration_ms=total_duration_ms,
            avg_latency_ms=avg_latency,
            success_count=success_count,
            failure_count=failure_count,
        )

        logger.info(
            f"Benchmark '{report.benchmark_name}' complete: "
            f"{success_count}/{len(sample_results)} succeeded, "
            f"avg_latency={avg_latency:.1f}ms"
        )
        return report

    async def _run_one(self, idx: int, sample: EvalSample) -> SampleResult:
        """Execute one sample with timeout protection."""
        start = time.perf_counter()
        try:
            state = await asyncio.wait_for(
                self.workflow_fn(sample.query, sample.metadata),
                timeout=self.timeout_seconds,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return self.evaluator.evaluate(
                state, sample, sample_index=idx, latency_ms=latency_ms,
            )
        except TimeoutError:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"Sample {idx} timed out after {self.timeout_seconds}s"
            )
            return SampleResult(
                sample_index=idx,
                query=sample.query,
                answer="",
                latency_ms=latency_ms,
                error=f"Timeout after {self.timeout_seconds}s",
                aborted=True,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Sample {idx} failed: {exc}", exc_info=True)
            return SampleResult(
                sample_index=idx,
                query=sample.query,
                answer="",
                latency_ms=latency_ms,
                error=str(exc),
            )
