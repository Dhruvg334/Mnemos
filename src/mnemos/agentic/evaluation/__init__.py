"""Production evaluation framework for the Mnemos AI investigation pipeline.

This package provides benchmarking, metric computation, evaluation
orchestration, and reporting for the full agentic workflow.
"""

from __future__ import annotations

from mnemos.agentic.evaluation.evaluator import InvestigationEvaluator
from mnemos.agentic.evaluation.metrics import MetricAggregator, ProductionMetrics
from mnemos.agentic.evaluation.models import (
    BenchmarkReport,
    ComparisonReport,
    EvalDataset,
    EvalPipelineType,
    EvalSample,
    EvaluationRun,
    MetricResult,
    SampleResult,
)
from mnemos.agentic.evaluation.reporter import EvalReporter
from mnemos.agentic.evaluation.runner import EvalRunner
from mnemos.agentic.evaluation.tool_selection import (
    TOOL_SELECTION_POLICIES,
    ToolSelectionEvaluation,
    ToolSelectionPolicy,
    evaluate_tool_trajectory,
)

__all__ = [
    "BenchmarkReport",
    "ComparisonReport",
    "EvalDataset",
    "EvalPipelineType",
    "EvalReporter",
    "EvalRunner",
    "EvalSample",
    "EvaluationRun",
    "InvestigationEvaluator",
    "MetricAggregator",
    "MetricResult",
    "ProductionMetrics",
    "SampleResult",
    "TOOL_SELECTION_POLICIES",
    "ToolSelectionEvaluation",
    "ToolSelectionPolicy",
    "evaluate_tool_trajectory",
]
