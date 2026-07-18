import asyncio
from typing import Any

from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from mnemos.agentic.config import agent_settings
from mnemos.agentic.evaluation.interfaces import EvaluationResult, RAGEvaluator
from mnemos.agentic.evaluation.models import EvalSample, MetricResult, SampleResult
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("ragas_evaluator")


class RagasEvaluatorImpl(RAGEvaluator):
    """
    Concrete RAGAS evaluator for Mnemos.
    Uses the project's primary LLM and Embedding configurations.
    """

    def __init__(self) -> None:
        # Configure the critic LLM for RAGAS evaluation
        self.critic_llm = ChatOpenAI(
            model=agent_settings.primary_llm.model_name,
            temperature=0,
            openai_api_key=agent_settings.primary_llm.api_key,
            base_url=agent_settings.primary_llm.base_url,
        )
        self.embeddings = OpenAIEmbeddings(
            model=agent_settings.embedding_model, openai_api_key=agent_settings.primary_llm.api_key
        )

        self.metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

    async def evaluate_sample(self, sample: EvalSample, result: SampleResult) -> list[MetricResult]:
        """
        Runs RAGAS metrics on a single sample result.
        """
        # RAGAS evaluate is blocking, so we run it in an executor
        data = {
            "question": [sample.query],
            "answer": [result.answer],
            "contexts": [result.retrieved_contexts],
            "ground_truth": [sample.ground_truth] if sample.ground_truth else [None],
        }

        dataset = Dataset.from_dict(data)

        try:
            loop = asyncio.get_event_loop()
            score_results = await loop.run_in_executor(
                None,
                lambda: evaluate(
                    dataset, metrics=self.metrics, llm=self.critic_llm, embeddings=self.embeddings
                ),
            )

            metric_results: list[MetricResult] = []
            for name, score in score_results.items():
                metric_results.append(
                    MetricResult(
                        name=name,
                        score=float(score),
                        reasoning=f"Calculated via RAGAS using {agent_settings.primary_llm.model_name} as critic.",
                    )
                )

            return metric_results
        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {str(e)}", exc_info=True)
            return []

    async def evaluate(
        self, input_data: Any, output_data: Any, context: dict[str, Any]
    ) -> list[EvaluationResult]:
        raise NotImplementedError("Use evaluate_sample() instead")

    async def evaluate_faithfulness(self, answer: str, context: list[str]) -> EvaluationResult:
        raise NotImplementedError("Use evaluate_sample() instead")

    async def evaluate_relevance(self, query: str, answer: str) -> EvaluationResult:
        raise NotImplementedError("Use evaluate_sample() instead")
