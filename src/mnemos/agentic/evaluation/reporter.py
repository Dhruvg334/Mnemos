from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from mnemos.agentic.evaluation.models import (
    BenchmarkReport,
    ComparisonReport,
)


def _deterministic_id(*parts: str) -> str:
    """Generate a deterministic ID from the given parts.

    Unlike uuid4(), this produces the same ID for the same inputs,
    enabling reproducible benchmarks and comparisons.
    """
    combined = "|".join(str(p) for p in parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _deterministic_timestamp(*parts: str) -> float:
    combined = "|".join(str(p) for p in parts)
    h = hashlib.sha256(combined.encode()).hexdigest()[:8]
    return int(h, 16) / 16_777_216


class EvalReporter:
    """Generate human-readable and machine-parsable reports from benchmark data.

    All public methods are pure functions that accept model instances and
    return formatted strings without side effects.
    """

    # ------------------------------------------------------------------
    # JSON serialisation
    # ------------------------------------------------------------------

    @staticmethod
    def to_json(report: BenchmarkReport | ComparisonReport) -> str:
        """Serialise a report to a JSON string with 2-space indentation."""
        return report.model_dump_json(indent=2)

    @staticmethod
    def to_dict(report: BenchmarkReport | ComparisonReport) -> dict[str, Any]:
        """Convert a report to a plain dictionary."""
        return report.model_dump(mode="json")

    # ------------------------------------------------------------------
    # Markdown generation — single benchmark
    # ------------------------------------------------------------------

    @staticmethod
    def to_markdown(report: BenchmarkReport) -> str:
        """Produce a full Markdown report for a single benchmark run."""
        lines: list[str] = []
        lines.append(f"# Benchmark Report: {report.benchmark_name}\n")
        lines.append(f"- **Benchmark ID**: `{report.benchmark_id}`")
        lines.append(f"- **Pipeline Type**: `{report.pipeline_type.value}`")
        lines.append(f"- **Dataset**: {report.dataset_name}")
        lines.append(f"- **Timestamp**: {report.timestamp.isoformat()}")
        lines.append(f"- **Total Duration**: {report.total_duration_ms:.1f} ms")
        lines.append(f"- **Avg Latency**: {report.avg_latency_ms:.1f} ms")
        lines.append(
            f"- **Samples**: {report.success_count} succeeded, "
            f"{report.failure_count} failed"
        )
        lines.append("")

        # Summary metrics table
        lines.append("## Summary Metrics\n")
        lines.append("| Metric | Value |")
        lines.append("| --- | --- |")
        for name, value in sorted(report.summary_metrics.items()):
            lines.append(f"| {name} | {value:.4f} |")
        lines.append("")

        # Per-sample detail
        lines.append("## Sample Results\n")
        for sr in report.sample_results:
            status_icon = "PASS" if sr.error is None else "FAIL"
            lines.append(f"### Sample {sr.sample_index + 1} [{status_icon}]\n")
            lines.append(f"- **Query**: {sr.query}")
            lines.append(f"- **Latency**: {sr.latency_ms:.1f} ms")
            if sr.error:
                lines.append(f"- **Error**: {sr.error}")
            lines.append(f"- **Phase**: {sr.phase or 'N/A'}")
            lines.append(f"- **Claims**: {sr.claim_count} total, {sr.grounded_claim_count} grounded")
            lines.append(f"- **Hallucination**: {'detected' if sr.hallucination_detected else 'none'}")
            lines.append("")

            if sr.metrics:
                lines.append("| Metric | Score | Reasoning |")
                lines.append("| --- | --- | --- |")
                for m in sr.metrics:
                    reasoning = (m.reasoning or "").replace("|", "\\|")
                    lines.append(f"| {m.name} | {m.score:.4f} | {reasoning} |")
                lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Markdown generation — comparison
    # ------------------------------------------------------------------

    @staticmethod
    def compare(
        primary: BenchmarkReport,
        secondary: BenchmarkReport,
    ) -> ComparisonReport:
        """Build a ``ComparisonReport`` computing percentage lift/drop.

        *primary* is the system under test and *secondary* is the baseline.
        A positive delta means primary outperformed secondary.
        """
        deltas: dict[str, float] = {}
        all_keys = set(primary.summary_metrics.keys()) | set(secondary.summary_metrics.keys())

        for key in all_keys:
            val_p = primary.summary_metrics.get(key, 0.0)
            val_s = secondary.summary_metrics.get(key, 0.0)
            if val_s != 0.0:
                deltas[key] = ((val_p - val_s) / abs(val_s)) * 100.0
            elif val_p != 0.0:
                deltas[key] = 100.0
            else:
                deltas[key] = 0.0

        return ComparisonReport(
            comparison_id=_deterministic_id(
                primary.benchmark_id, secondary.benchmark_id
            ),
            name=f"{primary.benchmark_name} vs {secondary.benchmark_name}",
            report_primary=primary,
            report_secondary=secondary,
            deltas=deltas,
            timestamp=datetime.fromtimestamp(
                _deterministic_timestamp(
                    primary.benchmark_id, secondary.benchmark_id
                ),
                tz=UTC,
            ),
        )

    @staticmethod
    def comparison_to_markdown(comparison: ComparisonReport) -> str:
        """Produce a Markdown report for a comparison between two benchmarks."""
        lines: list[str] = []
        lines.append(f"# Comparison Report: {comparison.name}\n")
        lines.append(f"- **Comparison ID**: `{comparison.comparison_id}`")
        lines.append(f"- **Timestamp**: {comparison.timestamp.isoformat()}")
        lines.append(
            f"- **Primary**: {comparison.report_primary.benchmark_name} "
            f"(`{comparison.report_primary.pipeline_type.value}`)"
        )
        lines.append(
            f"- **Secondary**: {comparison.report_secondary.benchmark_name} "
            f"(`{comparison.report_secondary.pipeline_type.value}`)"
        )
        lines.append("")

        lines.append("## Metric Deltas (Primary vs Secondary)\n")
        lines.append("| Metric | Primary | Secondary | Delta (%) |")
        lines.append("| --- | --- | --- | --- |")

        for key in sorted(comparison.deltas.keys()):
            val_p = comparison.report_primary.summary_metrics.get(key, 0.0)
            val_s = comparison.report_secondary.summary_metrics.get(key, 0.0)
            delta = comparison.deltas[key]
            direction = "+" if delta >= 0 else ""
            lines.append(
                f"| {key} | {val_p:.4f} | {val_s:.4f} | {direction}{delta:.2f}% |"
            )

        lines.append("")

        # Aggregate lift
        if comparison.deltas:
            avg_delta = sum(comparison.deltas.values()) / len(comparison.deltas)
            lines.append(f"**Average lift across all metrics: {avg_delta:+.2f}%**\n")

        return "\n".join(lines)
