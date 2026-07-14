from abc import ABC, abstractmethod
from typing import Any, Dict, List
from pydantic import BaseModel, Field

class EvaluationResult(BaseModel):
    metric_name: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class BaseEvaluator(ABC):
    """
    Abstract interface for evaluating agent outputs and retrieval quality.
    """
    @abstractmethod
    async def evaluate(self, input_data: Any, output_data: Any, context: Dict[str, Any]) -> List[EvaluationResult]:
        """Run evaluation metrics on the provided data."""
        pass

class RAGEvaluator(BaseEvaluator):
    """
    Specialized evaluator for Retrieval Augmented Generation.
    Evaluates faithfulness, relevance, and groundedness.
    """
    @abstractmethod
    async def evaluate_faithfulness(self, answer: str, context: List[str]) -> EvaluationResult:
        pass

    @abstractmethod
    async def evaluate_relevance(self, query: str, answer: str) -> EvaluationResult:
        pass
