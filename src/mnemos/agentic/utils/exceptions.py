class AgenticError(Exception):
    """Base exception for all AI/Agentic layer errors."""
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class RetrievalError(AgenticError):
    """Raised when retrieval from vector or graph fails."""
    pass


class ReasoningError(AgenticError):
    """Raised when the LLM or agent workflow fails to reason correctly."""
    pass


class VerificationError(AgenticError):
    """Raised when evidence verification fails."""
    pass


class ConfigurationError(AgenticError):
    """Raised when agentic components are misconfigured."""
    pass
