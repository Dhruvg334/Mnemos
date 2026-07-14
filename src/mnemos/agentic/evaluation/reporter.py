from mnemos.agentic.evaluation.models import BenchmarkReport, ComparisonReport


class EvaluationReporter:
    """
    Generates structured human-readable and machine-parsable reports
    from benchmark results.
    """

    @staticmethod
    def generate_json_report(report: BenchmarkReport) -> str:
        """Serializes the benchmark report to a JSON string."""
        return report.model_dump_json(indent=2)

    @staticmethod
    def compare_benchmarks(report_mnemos: BenchmarkReport, report_baseline: BenchmarkReport) -> ComparisonReport:
        """
        Compares the Mnemos GraphRAG performance against a baseline.
        Calculates deltas for all common metrics.
        """
        deltas = {}

        m1 = report_mnemos.summary_metrics
        m2 = report_baseline.summary_metrics

        # Calculate percentage lift for shared metrics
        all_metrics = set(m1.keys()).union(set(m2.keys()))
        for metric in all_metrics:
            if metric in m1 and metric in m2:
                if m2[metric] != 0:
                    deltas[metric] = ((m1[metric] - m2[metric]) / m2[metric]) * 100
                else:
                    deltas[metric] = 0.0

        return ComparisonReport(
            name=f"Comparison: {report_mnemos.benchmark_name} vs {report_baseline.benchmark_name}",
            report_mnemos=report_mnemos,
            report_baseline=report_baseline,
            deltas=deltas
        )

    @staticmethod
    def summarize_to_markdown(report: BenchmarkReport) -> str:
        """Generates a Markdown summary of the benchmark."""
        md = f"# Benchmark Report: {report.benchmark_name}\n\n"
        md += f"- **Pipeline Type**: {report.pipeline_type}\n"
        md += f"- **Timestamp**: {report.timestamp}\n"
        md += f"- **Dataset**: {report.dataset_name}\n\n"

        md += "## Summary Metrics\n\n"
        md += "| Metric | Score |\n"
        md += "| --- | --- |\n"
        for name, score in report.summary_metrics.items():
            md += f"| {name} | {score:.4f} |\n"

        md += "\n## Sample Results (First 5)\n\n"
        for i, res in enumerate(report.sample_results[:5]):
            md += f"### Sample {i+1}\n"
            md += f"- **Query**: {res.sample.query}\n"
            md += f"- **Latency**: {res.latency_ms:.2f}ms\n"
            md += f"- **Grounded Rate**: {res.grounded_answer_rate:.2f}\n"
            md += f"- **Hallucination Detected**: {res.hallucination_detected}\n\n"

        return md
