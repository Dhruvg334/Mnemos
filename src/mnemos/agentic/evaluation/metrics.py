from __future__ import annotations

from typing import Any

from mnemos.agentic.evaluation.models import MetricResult
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    ComplianceCheckResult,
    GroundedClaim,
)


class ProductionMetrics:
    """Collection of 10 production evaluation metrics for the Mnemos investigation pipeline.

    Every method returns a ``MetricResult`` with a normalised score in [0, 1] and
    a human-readable reasoning string.  Edge cases (empty inputs, division by zero)
    are handled explicitly so that callers never need guard clauses.
    """

    # ------------------------------------------------------------------
    # 1. Routing Accuracy
    # ------------------------------------------------------------------

    @staticmethod
    def routing_accuracy(
        predicted_intent: str | None,
        expected_intent: str | None,
    ) -> MetricResult:
        """Measure whether the query router selected the correct intent.

        Returns a perfect score when both values are identical, zero otherwise.
        A ``None`` predicted intent is treated as a misclassification unless the
        expected intent is also ``None``.
        """
        if expected_intent is None:
            score = 1.0
            reasoning = "No expected intent provided; defaulting to perfect score."
        elif predicted_intent is None:
            score = 0.0
            reasoning = "Router produced no intent prediction."
        elif predicted_intent.lower().strip() == expected_intent.lower().strip():
            score = 1.0
            reasoning = f"Predicted intent '{predicted_intent}' matches expected '{expected_intent}'."
        else:
            score = 0.0
            reasoning = (
                f"Predicted intent '{predicted_intent}' does not match "
                f"expected '{expected_intent}'."
            )

        return MetricResult(
            name="routing_accuracy",
            score=score,
            reasoning=reasoning,
            metadata={
                "predicted": predicted_intent,
                "expected": expected_intent,
            },
        )

    # ------------------------------------------------------------------
    # 2. Retrieval Recall@K
    # ------------------------------------------------------------------

    @staticmethod
    def retrieval_recall(
        retrieved_doc_ids: list[str],
        expected_doc_ids: list[str],
    ) -> MetricResult:
        """Compute recall of expected documents in the retrieved set.

        If no expected documents are specified the metric is not applicable and
        returns a score of 1.0 (no penalty).  Duplicate retrieved IDs are
        collapsed into a set before evaluation.
        """
        if not expected_doc_ids:
            return MetricResult(
                name="retrieval_recall",
                score=1.0,
                reasoning="No expected documents specified; recall not applicable.",
            )

        expected_set = set(expected_doc_ids)
        retrieved_set = set(retrieved_doc_ids)
        if not expected_set:
            return MetricResult(
                name="retrieval_recall",
                score=1.0,
                reasoning="Expected document set is empty.",
            )

        found = expected_set & retrieved_set
        score = len(found) / len(expected_set)

        missing = expected_set - retrieved_set
        reasoning = (
            f"Retrieved {len(found)} of {len(expected_set)} expected documents."
        )
        if missing:
            reasoning += f" Missing: {sorted(missing)}."

        return MetricResult(
            name="retrieval_recall",
            score=score,
            reasoning=reasoning,
            metadata={
                "found_count": len(found),
                "expected_count": len(expected_set),
                "missing": sorted(missing),
            },
        )

    # ------------------------------------------------------------------
    # 3. Graph Retrieval Quality
    # ------------------------------------------------------------------

    @staticmethod
    def graph_retrieval_quality(
        graph_nodes: list[str],
        expected_entities: list[str],
    ) -> MetricResult:
        """Evaluate quality of knowledge-graph traversal by node coverage.

        A score of 1.0 means every expected entity was found among the
        retrieved graph nodes.  If no entities are expected the metric
        defaults to 1.0.
        """
        if not expected_entities:
            return MetricResult(
                name="graph_retrieval_quality",
                score=1.0,
                reasoning="No expected entities specified; graph retrieval not applicable.",
            )

        expected_set = set(expected_entities)
        node_set = set(graph_nodes)
        found = expected_set & node_set
        score = len(found) / len(expected_set)

        missing = expected_set - node_set
        reasoning = (
            f"Graph traversal found {len(found)} of {len(expected_set)} "
            f"expected entities."
        )
        if missing:
            reasoning += f" Missing entities: {sorted(missing)}."

        return MetricResult(
            name="graph_retrieval_quality",
            score=score,
            reasoning=reasoning,
            metadata={
                "found_count": len(found),
                "expected_count": len(expected_set),
                "missing": sorted(missing),
            },
        )

    # ------------------------------------------------------------------
    # 4. Citation Precision
    # ------------------------------------------------------------------

    @staticmethod
    def citation_precision(
        citations: list[Citation],
        expected_citation_ids: list[str],
    ) -> MetricResult:
        """Measure precision of citations against an expected set.

        Precision = |cited & expected| / |cited|.  When no citations are
        produced the score is 0.0 (a system that cites nothing cannot be
        precise).  When no expected IDs are provided the metric is not
        applicable and returns 1.0.
        """
        if not expected_citation_ids:
            return MetricResult(
                name="citation_precision",
                score=1.0,
                reasoning="No expected citations specified; precision not applicable.",
            )

        cited_ids = [c.citation_id for c in citations]
        if not cited_ids:
            return MetricResult(
                name="citation_precision",
                score=0.0,
                reasoning="No citations produced; precision is 0.",
                metadata={"cited_count": 0, "expected_count": len(expected_citation_ids)},
            )

        expected_set = set(expected_citation_ids)
        cited_set = set(cited_ids)
        correct = expected_set & cited_set
        score = len(correct) / len(cited_set) if cited_set else 0.0

        reasoning = (
            f"Citation precision: {len(correct)} of {len(cited_set)} "
            f"cited IDs are in the expected set."
        )
        spurious = cited_set - expected_set
        if spurious:
            reasoning += f" Spurious: {sorted(spurious)}."

        return MetricResult(
            name="citation_precision",
            score=score,
            reasoning=reasoning,
            metadata={
                "correct_count": len(correct),
                "cited_count": len(cited_set),
                "spurious": sorted(spurious),
            },
        )

    # ------------------------------------------------------------------
    # 5. Grounded Answer Rate
    # ------------------------------------------------------------------

    @staticmethod
    def grounded_answer_rate(
        claims: list[GroundedClaim],
    ) -> MetricResult:
        """Fraction of SUPPORTED claims that have at least one verified evidence source.

        A claim is considered *grounded* when its status is ``SUPPORTED`` and it
        has at least one ``EvidenceSource`` attached.  When no claims exist the
        metric returns 1.0 (nothing to evaluate).
        """
        if not claims:
            return MetricResult(
                name="grounded_answer_rate",
                score=1.0,
                reasoning="No claims produced; grounded rate defaults to 1.0.",
            )

        supported = [c for c in claims if c.status == ClaimSupportStatus.SUPPORTED]
        if not supported:
            return MetricResult(
                name="grounded_answer_rate",
                score=1.0,
                reasoning="No SUPPORTED claims; grounded rate defaults to 1.0.",
            )

        grounded = [c for c in supported if len(c.sources) > 0]
        score = len(grounded) / len(supported)

        reasoning = (
            f"{len(grounded)} of {len(supported)} SUPPORTED claims have "
            f"verified evidence sources."
        )
        ungrounded_ids = [c.claim_id for c in supported if not c.sources]
        if ungrounded_ids:
            reasoning += f" Ungrounded claim IDs: {ungrounded_ids}."

        return MetricResult(
            name="grounded_answer_rate",
            score=score,
            reasoning=reasoning,
            metadata={
                "grounded_count": len(grounded),
                "supported_count": len(supported),
                "total_claims": len(claims),
            },
        )

    # ------------------------------------------------------------------
    # 6. Abstention Quality
    # ------------------------------------------------------------------

    @staticmethod
    def abstention_quality(
        abstained: bool,
        ground_truth_available: bool,
    ) -> MetricResult:
        """Evaluate the quality of an abstention decision.

        The system should abstain when ground truth is *not* available (correct
        abstention) and should *not* abstain when ground truth is available
        (correct non-abstention).  All four quadrants are scored:

        +-----------+---------+-------+
        | Abstained | GT Avail| Score |
        +-----------+---------+-------+
        | True      | False   | 1.0   |  ← correct abstention
        | False     | True    | 1.0   |  ← correct non-abstention
        | True      | True    | 0.0   |  ← unnecessary abstention
        | False     | False   | 0.25  |  ← answering without evidence
        +-----------+---------+-------+
        """
        if abstained and not ground_truth_available:
            score = 1.0
            reasoning = "Correctly abstained when ground truth is unavailable."
        elif not abstained and ground_truth_available:
            score = 1.0
            reasoning = "Correctly produced an answer when ground truth is available."
        elif abstained and ground_truth_available:
            score = 0.0
            reasoning = "Unnecessarily abstained despite ground truth being available."
        else:
            score = 0.25
            reasoning = "Produced an answer without ground truth available; partial credit for attempting."

        return MetricResult(
            name="abstention_quality",
            score=score,
            reasoning=reasoning,
            metadata={
                "abstained": abstained,
                "ground_truth_available": ground_truth_available,
            },
        )

    # ------------------------------------------------------------------
    # 7. Tool Recovery
    # ------------------------------------------------------------------

    @staticmethod
    def tool_recovery(
        tool_calls: list[dict[str, Any]],
        failed_tool_calls: list[dict[str, Any]],
    ) -> MetricResult:
        """Measure recovery rate after tool-call failures.

        Recovery is defined as: (total_calls - failed_calls_after_retry) /
        total_calls.  The *failed_tool_calls* list should contain only those
        tool calls that ultimately failed after all retry attempts.  If no
        tool calls were made the metric returns 1.0.
        """
        total = len(tool_calls)
        if total == 0:
            return MetricResult(
                name="tool_recovery",
                score=1.0,
                reasoning="No tool calls made; recovery not applicable.",
            )

        final_failures = len(failed_tool_calls)
        score = (total - final_failures) / total

        reasoning = (
            f"{total - final_failures} of {total} tool calls succeeded "
            f"after retries."
        )
        if final_failures > 0:
            failed_names = [fc.get("tool_name", "unknown") for fc in failed_tool_calls]
            reasoning += f" Permanently failed: {failed_names}."

        return MetricResult(
            name="tool_recovery",
            score=score,
            reasoning=reasoning,
            metadata={
                "total_calls": total,
                "final_failures": final_failures,
            },
        )

    # ------------------------------------------------------------------
    # 8. Workflow Completion
    # ------------------------------------------------------------------

    @staticmethod
    def workflow_completion(
        is_complete: bool,
        termination_reason: str | None,
        expected_complete: bool = True,
    ) -> MetricResult:
        """Score whether the workflow reached the expected final state.

        Returns 1.0 when the workflow state matches expectations, 0.0
        otherwise.  A ``termination_reason`` is recorded for diagnostic
        purposes.
        """
        matched = is_complete == expected_complete
        score = 1.0 if matched else 0.0

        if matched:
            reasoning = (
                f"Workflow completion matches expectation "
                f"(complete={is_complete})."
            )
        else:
            reasoning = (
                f"Workflow completion mismatch: expected complete={expected_complete}, "
                f"got complete={is_complete}, reason={termination_reason!r}."
            )

        return MetricResult(
            name="workflow_completion",
            score=score,
            reasoning=reasoning,
            metadata={
                "is_complete": is_complete,
                "termination_reason": termination_reason,
                "expected_complete": expected_complete,
            },
        )

    # ------------------------------------------------------------------
    # 9. RCA Quality
    # ------------------------------------------------------------------

    @staticmethod
    def rca_quality(
        rca_output: str,
        expected_root_cause: str,
    ) -> MetricResult:
        """Evaluate root-cause analysis output via semantic overlap.

        Uses a token-overlap (Jaccard) heuristic between the normalised RCA
        output and the expected root cause.  This avoids LLM dependency while
        still providing a meaningful signal for exact/near-exact matches.
        """
        if not expected_root_cause:
            return MetricResult(
                name="rca_quality",
                score=1.0,
                reasoning="No expected root cause provided; RCA quality not applicable.",
            )

        if not rca_output:
            return MetricResult(
                name="rca_quality",
                score=0.0,
                reasoning="RCA output is empty.",
            )

        def _tokenise(text: str) -> set[str]:
            return set(text.lower().split())

        expected_tokens = _tokenise(expected_root_cause)
        output_tokens = _tokenise(rca_output)

        if not expected_tokens:
            return MetricResult(
                name="rca_quality",
                score=1.0,
                reasoning="Expected root cause contains no tokens.",
            )

        intersection = expected_tokens & output_tokens
        union = expected_tokens | output_tokens
        score = len(intersection) / len(union) if union else 0.0

        reasoning = (
            f"Jaccard overlap between RCA output and expected root cause: "
            f"{score:.4f} ({len(intersection)} shared tokens of {len(union)} total)."
        )

        return MetricResult(
            name="rca_quality",
            score=min(score, 1.0),
            reasoning=reasoning,
            metadata={
                "intersection_size": len(intersection),
                "union_size": len(union),
                "rca_length": len(rca_output),
            },
        )

    # ------------------------------------------------------------------
    # 10. Compliance Quality
    # ------------------------------------------------------------------

    @staticmethod
    def compliance_quality(
        compliance_checks: list[ComplianceCheckResult],
        expected_compliance: str | None,
    ) -> MetricResult:
        """Evaluate the quality of compliance-check results.

        When an ``expected_compliance`` status (``"pass"`` or ``"fail"``) is
        provided, the metric checks whether the majority of check results
        agree with it.  When no checks were produced the score is 0.0
        (failure to run checks).  When no expected status is provided the
        metric evaluates whether the checks are internally consistent (all
        pass, or a mix with at least one warning/fail documented).
        """
        if not compliance_checks:
            return MetricResult(
                name="compliance_quality",
                score=0.0,
                reasoning="No compliance checks were produced.",
            )

        statuses = [cc.status for cc in compliance_checks]
        pass_count = statuses.count("pass")
        fail_count = statuses.count("fail")
        warn_count = statuses.count("warning")
        total = len(statuses)

        if expected_compliance is not None:
            expected_lower = expected_compliance.lower().strip()
            if expected_lower == "pass":
                score = pass_count / total
                reasoning = (
                    f"Expected compliance 'pass': {pass_count}/{total} "
                    f"checks passed."
                )
            elif expected_lower == "fail":
                score = fail_count / total if total else 0.0
                reasoning = (
                    f"Expected compliance 'fail': {fail_count}/{total} "
                    f"checks failed."
                )
            else:
                score = 1.0
                reasoning = (
                    f"Expected compliance status '{expected_compliance}' "
                    f"recorded across {total} checks."
                )
        else:
            documented = pass_count + fail_count + warn_count
            score = documented / total if total else 0.0
            reasoning = (
                f"No expected status provided; {documented}/{total} "
                f"checks have a definitive status "
                f"(pass={pass_count}, fail={fail_count}, warn={warn_count})."
            )

        return MetricResult(
            name="compliance_quality",
            score=min(score, 1.0),
            reasoning=reasoning,
            metadata={
                "total_checks": total,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "warn_count": warn_count,
                "expected_compliance": expected_compliance,
            },
        )


class MetricAggregator:
    """Compute weighted averages across multiple ``MetricResult`` instances."""

    @staticmethod
    def weighted_average(
        metrics: list[MetricResult],
    ) -> float:
        """Return the weighted average score across all provided metrics.

        Weight defaults to 1.0 for metrics that do not specify an explicit
        weight.  Returns 0.0 when the metric list is empty.
        """
        if not metrics:
            return 0.0

        total_weight = sum(m.weight for m in metrics)
        if total_weight == 0.0:
            return 0.0

        return sum(m.score * m.weight for m in metrics) / total_weight

    @staticmethod
    def aggregate_by_name(
        metrics: list[MetricResult],
    ) -> dict[str, float]:
        """Compute the weighted average for each unique metric name.

        When multiple ``MetricResult`` entries share the same name (e.g. from
        multiple samples) they are averaged together weighted by their
        individual ``weight`` field.
        """
        buckets: dict[str, list[MetricResult]] = {}
        for m in metrics:
            buckets.setdefault(m.name, []).append(m)

        result: dict[str, float] = {}
        for name, entries in buckets.items():
            result[name] = MetricAggregator.weighted_average(entries)
        return result

    @staticmethod
    def compute_summary(
        metrics: list[MetricResult],
    ) -> dict[str, float]:
        """Produce a flat summary dictionary with per-metric averages and an overall score."""
        per_name = MetricAggregator.aggregate_by_name(metrics)
        overall = MetricAggregator.weighted_average(metrics)
        summary = {f"avg_{name}": score for name, score in per_name.items()}
        summary["overall_weighted_score"] = overall
        return summary
