import time
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.evaluation.industrial_eval import IndustrialEvaluator
from mnemos.agentic.evaluation.models import (
    BenchmarkReport,
    EvalDataset,
    EvalPipelineType,
    EvalSample,
    SampleResult,
)
from mnemos.agentic.evaluation.ragas_impl import RagasEvaluatorImpl
from mnemos.agentic.orchestrator import MnemosAIOrchestrator
from mnemos.agentic.schemas.base import ClaimSupportStatus
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("eval_runner")

class BenchmarkRunner:
    """
    Production-grade benchmark runner.
    Executes real queries through the AI Layer and calculates industrial lift.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = MnemosAIOrchestrator(db)
        self.ragas_evaluator = RagasEvaluatorImpl()
        self.industrial_evaluator = IndustrialEvaluator()

    async def run_benchmark(
        self,
        dataset: EvalDataset,
        pipeline_type: EvalPipelineType = EvalPipelineType.MNEMOS_GRAPH_RAG,
        benchmark_name: str | None = None
    ) -> BenchmarkReport:
        logger.info(f"Initiating benchmark: {benchmark_name or dataset.name}")

        sample_results: list[SampleResult] = []
        for sample in dataset.samples:
            try:
                result = await self._run_sample(sample, pipeline_type)
                sample_results.append(result)
            except Exception as e:
                logger.error(f"Sample evaluation failed for '{sample.query[:30]}': {e}")

        summary = self._calculate_summary(sample_results)

        return BenchmarkReport(
            benchmark_id=str(uuid.uuid4()),
            benchmark_name=benchmark_name or f"{dataset.name}_{datetime.now().strftime('%Y%m%d')}",
            pipeline_type=pipeline_type,
            dataset_name=dataset.name,
            summary_metrics=summary,
            sample_results=sample_results
        )

    async def _run_sample(self, sample: EvalSample, pipeline_type: EvalPipelineType) -> SampleResult:
        start_time = time.perf_counter()

        # 1. Execute real AI Layer Orchestration
        # In a real setup, we would trigger the orchestrator's run_query
        # For the runner, we need the raw state, so we call the workflow directly
        initial_state = {
            "query": sample.query,
            "context": {"site_id": sample.metadata.get("site_id"), "is_eval": True},
            "intent": None, "resolved_entities": [], "retrieval_plan": None,
            "evidence_bundle": None, "messages": [], "claims": [],
            "final_response": None, "steps_completed": [], "errors": []
        }

        # Invoke LangGraph
        final_state = await self.orchestrator.workflow.ainvoke(initial_state)
        response = final_state.get("final_response")
        latency_ms = (time.perf_counter() - start_time) * 1000

        # 2. Extract context and metrics
        bundle = final_state.get("evidence_bundle")
        retrieved_contexts = [e.text_excerpt for e in bundle.verified_evidence] if bundle else []
        retrieved_doc_ids = [e.provenance.document_id for e in bundle.verified_evidence] if bundle else []
        resolved_entities = [e.entity_id for e in final_state["resolved_entities"]]

        # Grounding metrics
        claims = response.claims if response else []
        grounded_claims = [c for c in claims if c.status == ClaimSupportStatus.SUPPORTED and c.sources]
        grounded_rate = len(grounded_claims) / len(claims) if claims else 1.0
        hallucination = any(c.status == ClaimSupportStatus.SUPPORTED and not c.sources for c in claims)

        sample_res = SampleResult(
            sample=sample,
            answer=response.answer if response else "ERROR: No response generated",
            retrieved_contexts=retrieved_contexts,
            retrieved_document_ids=retrieved_doc_ids,
            citations=[s.provenance.document_id for c in claims for s in c.sources],
            resolved_entities=resolved_entities,
            metrics=[],
            latency_ms=latency_ms,
            hallucination_detected=hallucination,
            grounded_answer_rate=grounded_rate
        )

        # 3. Calculate RAGAS and Industrial scores
        sample_res.metrics.extend(await self.industrial_evaluator.evaluate_sample(sample, sample_res))
        try:
            sample_res.metrics.extend(await self.ragas_evaluator.evaluate_sample(sample, sample_res))
        except Exception as e:
            logger.warning(f"RAGAS evaluation skipped for sample: {e}")

        return sample_res

    def _calculate_summary(self, results: list[SampleResult]) -> dict[str, float]:
        if not results:
            return {}
        metric_sums: dict[str, float] = {}
        metric_counts: dict[str, int] = {}

        for res in results:
            for m in res.metrics:
                metric_sums[m.name] = metric_sums.get(m.name, 0.0) + m.score
                metric_counts[m.name] = metric_counts.get(m.name, 0) + 1

        summary = {f"avg_{name}": val/metric_counts[name] for name, val in metric_sums.items()}
        summary["avg_latency_ms"] = sum(r.latency_ms for r in results) / len(results)
        summary["total_samples"] = float(len(results))
        return summary
