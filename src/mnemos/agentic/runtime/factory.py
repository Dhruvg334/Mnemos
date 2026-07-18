"""Canonical construction root for the Mnemos investigation runtime.

All production callers must create the agentic runtime through this module.
Centralising construction prevents API workers, tests, and future background
workers from silently wiring different orchestration graphs or dependency
sets.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.runtime.workflow import InvestigationPipeline


def build_investigation_pipeline(*, db: AsyncSession) -> InvestigationPipeline:
    """Build the single production investigation pipeline.

    Durable checkpoint, approval, audit, event, and idempotency dependencies
    will be attached here as those phases are completed.  Callers must not
    instantiate alternative workflow builders or the legacy LangGraph graph.
    """

    return InvestigationPipeline(db=db)
