import asyncio
from typing import Any, Dict, List, Optional
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from mnemos.agentic.evaluation.interfaces import RAGEvaluator, EvaluationResult
from mnemos.agentic.evaluation.models import EvalSample, SampleResult, MetricResult
from mnemos.agentic.config import agent_settings
from mnemos.agentic.utils.logging import setup_agent_logger

logger = setup_agent_logger("ragas_evaluator")

class RagasEvaluatorImpl(RAGEvaluator):
    """
    Concrete RAGAS evaluator for Mnemos.
    Uses the project's primary LLM and Embedding configurations.
    """

    def __init__(self):
        # Configure the critic LLM for RAGAS evaluation
        self.critic_llm = ChatOpenAI(
            model=agent_settings.primary_llm.model_name,
            temperature=0,
            openai_api_key=agent_settings.primary_llm.api_key,
            base_url=agent_settings.primary_llm.base_url
        )
        self.embeddings = OpenAIEmbeddings(
            model=agent_settings.embedding_model,
            openai_api_key=agent_settings.primary_llm.api_key
        )

        self.metrics = [
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall
        ]

    async def evaluate_sample(self, sample: EvalSample, result: SampleResult) -> List[MetricResult]:
        """
        Runs RAGAS metrics on a single sample result.
        """
        # RAGAS evaluate is blocking, so we wrap it in a thread if necessary
        # Prepare data in RAGAS format
        data = {
            "question": [sample.query],
            "answer": [result.answer],
            "contexts": [result.retrieved_contexts],
            "ground_truth": [sample.ground_truth] if sample.ground_truth else [None]
        }

        dataset = Dataset.from_dict(data)

        # Execute RAGAS
        loop = asyncio.get_event_loop()
        score_results = await loop.run_in_executor(
            None,
            lambda: evaluate(
                dataset,
                metrics=self.metrics,
                llm=self.critic_llm,
                embeddings=self.embeddings
            )
        )

        metric_results = []
        for name, score in score_results.items():
            metric_results.append(MetricResult(
                name=name,
                score=float(score),
                reasoning=f"Calculated via RAGAS using {agent_settings.primary_llm.model_name} as critic."
            ))

        return metric_results

    async def evaluate(self, input_data: Any, output_data: Any, context: Dict[str, Any]) -> List[EvaluationResult]:
        return []

    async def evaluate_faithfulness(self, answer: str, context: List[str]) -> EvaluationResult:
        return EvaluationResult(metric_name="faithfulness", score=0.0, reasoning="Use evaluate_sample")

    async def evaluate_relevance(self, query: str, answer: str) -> EvaluationResult:
        return EvaluationResult(metric_name="answer_relevancy", score=0.0, reasoning="Use evaluate_sample")
