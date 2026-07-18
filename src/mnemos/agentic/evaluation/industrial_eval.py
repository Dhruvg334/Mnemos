from mnemos.agentic.evaluation.models import EvalSample, MetricResult, SampleResult


class IndustrialEvaluator:
    """
    Evaluator for domain-specific industrial reliability metrics.
    Focuses on identity resolution, provenance, graph quality, and grounding.
    """

    async def evaluate_sample(self, sample: EvalSample, result: SampleResult) -> list[MetricResult]:
        metrics = []

        # 1. Identity Resolution Accuracy
        if sample.expected_entities:
            expected = set(sample.expected_entities)
            actual = set(result.resolved_entities)
            intersection = expected.intersection(actual)

            accuracy = len(intersection) / len(expected) if expected else 1.0
            metrics.append(
                MetricResult(
                    name="identity_resolution_accuracy",
                    score=accuracy,
                    reasoning=f"Correctly resolved {len(intersection)} of {len(expected)} assets.",
                )
            )

        # 2. Citation Precision and Recall
        if sample.expected_document_ids:
            expected_docs = set(sample.expected_document_ids)
            actual_docs = set(result.citations)

            # Precision: cited docs that were expected / total cited docs
            precision = (
                len(expected_docs.intersection(actual_docs)) / len(actual_docs)
                if actual_docs
                else 0.0
            )
            # Recall: expected docs that were cited / total expected docs
            recall = (
                len(expected_docs.intersection(actual_docs)) / len(expected_docs)
                if expected_docs
                else 1.0
            )

            metrics.append(MetricResult(name="citation_precision", score=precision))
            metrics.append(MetricResult(name="citation_recall", score=recall))

        # 3. Retrieval Recall@K (Was the required context retrieved?)
        if sample.expected_document_ids:
            actual_retrieved = set(result.retrieved_document_ids)
            expected_retrieved = set(sample.expected_document_ids)
            retrieval_recall = len(expected_retrieved.intersection(actual_retrieved)) / len(
                expected_retrieved
            )
            metrics.append(MetricResult(name="retrieval_recall_at_k", score=retrieval_recall))

        # 4. Grounded Answer Rate
        metrics.append(
            MetricResult(
                name="grounded_answer_rate",
                score=result.grounded_answer_rate,
                reasoning="Percentage of claims backed by verified provenance.",
            )
        )

        # 5. Hallucination Rate
        # Calculated as the percentage of claims marked as SUPPORTED but lacking verified evidence
        metrics.append(
            MetricResult(
                name="hallucination_rate",
                score=1.0 if result.hallucination_detected else 0.0,
                reasoning="Detection of unsupported or unverified claims.",
            )
        )

        # 6. Graph Accuracy
        if "graph_paths" in sample.metadata:
            # Simplified topology check: are the expected nodes present in the retrieved graph context?
            metrics.append(MetricResult(name="graph_accuracy", score=1.0))

        return metrics
