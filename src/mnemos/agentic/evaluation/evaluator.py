from __future__ import annotations

from typing import Any

from mnemos.agentic.evaluation.metrics import ProductionMetrics
from mnemos.agentic.evaluation.models import EvalSample, MetricResult, SampleResult
from mnemos.agentic.runtime.types import AgentInvocationMetadata
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("evaluator")


class InvestigationEvaluator:
    """Evaluates a completed ``InvestigationState`` against an ``EvalSample``.

    Extracts intent, retrieved documents, citations, claims, tool-call
    records, and workflow metadata from the state and runs all 10
    production metrics.  Returns a fully populated ``SampleResult``.
    """

    def evaluate(
        self,
        state: dict[str, Any],
        sample: EvalSample,
        sample_index: int = 0,
        latency_ms: float = 0.0,
    ) -> SampleResult:
        """Run all production metrics against a single investigation state.

        Parameters
        ----------
        state:
            The final ``InvestigationState`` dict produced by the workflow.
        sample:
            Ground-truth annotations for this query.
        sample_index:
            Position of this sample in the dataset (for reporting).
        latency_ms:
            Wall-clock time for the workflow invocation in milliseconds.
        """
        phase = state.get("phase")
        if phase is None:
            phase_str = None
        elif isinstance(phase, str):
            phase_str = phase
        else:
            phase_str = phase.value

        # --- extract data from state ---
        predicted_intent = self._extract_intent(state)
        retrieved_docs = self._extract_retrieved_doc_ids(state)
        graph_nodes = self._extract_graph_nodes(state)
        citations = self._extract_citations(state)
        claims = self._extract_claims(state)
        tool_calls, failed_tool_calls = self._extract_tool_calls(state)
        answer = self._extract_answer(state)
        is_complete = bool(state.get("is_complete", False))
        termination_reason = state.get("termination_reason")
        abstained = bool(state.get("should_abstain", False))
        ground_truth_available = sample.ground_truth_available

        # --- run metrics ---
        metrics: list[MetricResult] = []

        metrics.append(ProductionMetrics.routing_accuracy(predicted_intent, sample.expected_intent))
        metrics.append(
            ProductionMetrics.retrieval_recall(retrieved_docs, sample.expected_document_ids)
        )
        metrics.append(
            ProductionMetrics.graph_retrieval_quality(graph_nodes, sample.expected_entities)
        )
        metrics.append(
            ProductionMetrics.citation_precision(citations, sample.expected_citation_ids)
        )
        metrics.append(ProductionMetrics.grounded_answer_rate(claims))
        metrics.append(ProductionMetrics.abstention_quality(abstained, ground_truth_available))
        metrics.append(ProductionMetrics.tool_recovery(tool_calls, failed_tool_calls))
        metrics.append(
            ProductionMetrics.workflow_completion(
                is_complete,
                termination_reason.value
                if termination_reason is not None and hasattr(termination_reason, "value")
                else str(termination_reason)
                if termination_reason is not None
                else None,
            )
        )

        rca_output = self._extract_rca_output(state)
        metrics.append(ProductionMetrics.rca_quality(rca_output, sample.expected_root_cause or ""))

        compliance_checks = self._extract_compliance_checks(state)
        metrics.append(
            ProductionMetrics.compliance_quality(
                compliance_checks, sample.expected_compliance_status
            )
        )

        # --- build result ---
        ground_claim_count = sum(
            1 for c in claims if c.status.value == "supported" and len(c.sources) > 0
        )
        hallucination = any(c.status.value == "supported" and len(c.sources) == 0 for c in claims)

        resolved_entities = self._extract_resolved_entities(state)
        retrieved_contexts = self._extract_retrieved_contexts(state)

        return SampleResult(
            sample_index=sample_index,
            query=sample.query,
            answer=answer,
            latency_ms=latency_ms,
            metrics=metrics,
            retrieved_contexts=retrieved_contexts,
            retrieved_document_ids=retrieved_docs,
            resolved_entities=resolved_entities,
            citation_ids=[c.citation_id for c in citations],
            claim_count=len(claims),
            grounded_claim_count=ground_claim_count,
            hallucination_detected=hallucination,
            phase=phase_str,
            aborted=abstained,
        )

    def evaluate_batch(
        self,
        samples: list[EvalSample],
        states: list[dict[str, Any]],
        latencies_ms: list[float] | None = None,
    ) -> list[SampleResult]:
        """Evaluate multiple (sample, state) pairs.

        Parameters
        ----------
        samples:
            Ground-truth samples.
        states:
            Investigation states corresponding to each sample.
        latencies_ms:
            Optional per-sample latencies.  Defaults to zeros.

        Raises
        ------
        ValueError
            If ``samples`` and ``states`` have different lengths.
        """
        if len(samples) != len(states):
            raise ValueError(
                f"samples ({len(samples)}) and states ({len(states)}) must have equal length"
            )

        if latencies_ms is None:
            latencies_ms = [0.0] * len(samples)
        elif len(latencies_ms) != len(samples):
            raise ValueError(
                f"latencies_ms ({len(latencies_ms)}) must match samples ({len(samples)})"
            )

        results: list[SampleResult] = []
        for idx, (sample, state, latency) in enumerate(
            zip(samples, states, latencies_ms, strict=True)
        ):
            try:
                result = self.evaluate(state, sample, sample_index=idx, latency_ms=latency)
                results.append(result)
            except Exception as exc:
                logger.error(
                    f"Failed to evaluate sample {idx}: {exc}",
                    exc_info=True,
                )
                results.append(
                    SampleResult(
                        sample_index=idx,
                        query=sample.query,
                        answer="",
                        latency_ms=latency,
                        error=str(exc),
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_intent(state: dict[str, Any]) -> str | None:
        """Pull the classified intent from agent outputs or direct state."""
        router_output = state.get("agent_outputs", {}).get("query_router", {})
        intent = router_output.get("intent")
        if intent is not None:
            return str(intent)

        retrieval_plan = state.get("retrieval_plan")
        if retrieval_plan is not None and hasattr(retrieval_plan, "intent"):
            return str(retrieval_plan.intent.value)
        if isinstance(retrieval_plan, dict):
            intent_val = retrieval_plan.get("intent")
            if intent_val is not None:
                return str(intent_val)

        return None

    @staticmethod
    def _extract_retrieved_doc_ids(state: dict[str, Any]) -> list[str]:
        """Extract unique document IDs from evidence sources."""
        evidence_list = state.get("evidence", [])
        doc_ids: list[str] = []
        seen: set[str] = set()

        for item in evidence_list:
            sources = item.get("verified_evidence", []) if isinstance(item, dict) else []
            for src in sources:
                if not isinstance(src, dict):
                    continue
                prov = src.get("provenance", {})
                doc_id = prov.get("document_id") if isinstance(prov, dict) else None
                if doc_id and doc_id not in seen:
                    seen.add(doc_id)
                    doc_ids.append(doc_id)

        return doc_ids

    @staticmethod
    def _extract_graph_nodes(state: dict[str, Any]) -> list[str]:
        """Collect graph node IDs from evidence bundles."""
        evidence_list = state.get("evidence", [])
        nodes: list[str] = []
        seen: set[str] = set()

        for item in evidence_list:
            if not isinstance(item, dict):
                continue
            for rel in item.get("grounded_relationships", []):
                if not isinstance(rel, dict):
                    continue
                for key in ("source_id", "target_id"):
                    node_id = rel.get(key)
                    if node_id and node_id not in seen:
                        seen.add(node_id)
                        nodes.append(node_id)
            resolved = item.get("resolved_entities", [])
            for ent in resolved:
                if not isinstance(ent, dict):
                    continue
                eid = ent.get("entity_id")
                if eid and eid not in seen:
                    seen.add(eid)
                    nodes.append(eid)

        return nodes

    @staticmethod
    def _extract_citations(state: dict[str, Any]) -> list[Any]:
        """Collect Citation objects (or dicts) from evidence bundles."""
        evidence_list = state.get("evidence", [])
        citations: list[Any] = []
        seen: set[str] = set()

        for item in evidence_list:
            if not isinstance(item, dict):
                continue
            for cit in item.get("citations", []):
                cit_id = (
                    cit.get("citation_id", "")
                    if isinstance(cit, dict)
                    else getattr(cit, "citation_id", "")
                )
                if cit_id and cit_id not in seen:
                    seen.add(cit_id)
                    citations.append(cit)

        return citations

    @staticmethod
    def _extract_claims(state: dict[str, Any]) -> list[Any]:
        """Collect GroundedClaim objects (or dicts) from state."""
        raw_claims = state.get("claims", [])
        parsed: list[Any] = []
        for c in raw_claims:
            if isinstance(c, dict):
                parsed.append(
                    type(
                        "_G",
                        (),
                        {
                            "claim_id": c.get("claim_id", ""),
                            "status": type("_S", (), {"value": c.get("status", "uncertain")})(),
                            "sources": c.get("sources", []),
                        },
                    )()
                )
            else:
                parsed.append(c)
        return parsed

    @staticmethod
    def _extract_tool_calls(
        state: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Separate successful and failed tool calls from agent metadata."""
        all_calls: list[dict[str, Any]] = []
        failed_calls: list[dict[str, Any]] = []

        agent_metadata = state.get("agent_metadata", {})
        for _agent_name, meta in agent_metadata.items():
            if isinstance(meta, dict):
                calls = meta.get("tool_calls", [])
            elif isinstance(meta, AgentInvocationMetadata):
                calls = [tc.model_dump() for tc in meta.tool_calls]
            else:
                continue

            for tc in calls:
                tc_dict = tc if isinstance(tc, dict) else {"tool_name": str(tc)}
                all_calls.append(tc_dict)
                if not tc_dict.get("success", True):
                    failed_calls.append(tc_dict)

        return all_calls, failed_calls

    @staticmethod
    def _extract_answer(state: dict[str, Any]) -> str:
        """Pull the final answer text from agent outputs or direct state."""
        composer_output = state.get("agent_outputs", {}).get("response_composer", {})
        answer = composer_output.get("answer")
        if answer:
            return str(answer)

        final_response = state.get("final_response")
        if final_response is not None and hasattr(final_response, "answer"):
            return str(final_response.answer)
        if isinstance(final_response, dict):
            ans = final_response.get("answer")
            if ans:
                return str(ans)

        return ""

    @staticmethod
    def _extract_rca_output(state: dict[str, Any]) -> str:
        """Extract root-cause analysis output text."""
        rca_output = state.get("agent_outputs", {}).get("rca_agent", {})
        if isinstance(rca_output, dict):
            text = rca_output.get("reasoning_summary") or rca_output.get("answer") or ""
            if text:
                return str(text)
            hypotheses = rca_output.get("hypotheses", [])
            if hypotheses:
                parts = []
                for h in hypotheses:
                    if isinstance(h, dict):
                        parts.append(h.get("text", ""))
                    elif hasattr(h, "text"):
                        parts.append(h.text)
                return "\n".join(parts)
        return ""

    @staticmethod
    def _extract_compliance_checks(state: dict[str, Any]) -> list[Any]:
        """Extract compliance check results from agent outputs."""
        compliance_output = state.get("agent_outputs", {}).get("compliance_agent", {})
        if isinstance(compliance_output, dict):
            checks = compliance_output.get("compliance_checks", [])
            if not checks:
                checks = compliance_output.get("checks", [])
            return checks
        return []

    @staticmethod
    def _extract_resolved_entities(state: dict[str, Any]) -> list[str]:
        """Extract resolved entity IDs."""
        entities: list[str] = []
        seen: set[str] = set()

        evidence_list = state.get("evidence", [])
        for item in evidence_list:
            if not isinstance(item, dict):
                continue
            for ent in item.get("resolved_entities", []):
                if not isinstance(ent, dict):
                    continue
                eid = ent.get("entity_id")
                if eid and eid not in seen:
                    seen.add(eid)
                    entities.append(eid)

        return entities

    @staticmethod
    def _extract_retrieved_contexts(state: dict[str, Any]) -> list[str]:
        """Extract text excerpts from verified evidence."""
        contexts: list[str] = []
        evidence_list = state.get("evidence", [])
        for item in evidence_list:
            if not isinstance(item, dict):
                continue
            for src in item.get("verified_evidence", []):
                if isinstance(src, dict):
                    excerpt = src.get("text_excerpt", "")
                    if excerpt:
                        contexts.append(excerpt)
        return contexts
