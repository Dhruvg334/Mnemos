import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

# Context variable to correlate all logs for a single query across agents and retrievers
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="no-trace")


class StructuredLogger:
    """
    Production-grade structured logger for industrial AI operations.
    Supports trace propagation and high-fidelity event context.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(f"mnemos.agentic.{name}")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - [Trace: %(trace_id)s] - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _get_extra(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        full_extra = {"trace_id": trace_id_var.get()}
        if extra:
            full_extra.update(extra)
        return full_extra

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(msg, extra=self._get_extra(kwargs))

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(msg, extra=self._get_extra(kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(
            msg, extra=self._get_extra(kwargs), exc_info=kwargs.get("exc_info", False)
        )

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(msg, extra=self._get_extra(kwargs))

    def exception(self, msg: str, **kwargs: Any) -> None:
        self.logger.exception(msg, extra=self._get_extra(kwargs))


def setup_trace(trace_id: str | None = None) -> str:
    """Initializes a new trace context."""
    tid = trace_id or f"mnm_{uuid.uuid4().hex[:12]}"
    trace_id_var.set(tid)
    return tid


def get_trace_id() -> str:
    return trace_id_var.get()
