from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.core.config import settings
from mnemos.core.errors import AppError
from mnemos.models import Document, EvidenceRegion, Query
from mnemos.schemas.agent import AgentQueryResult


async def validate_agent_result(
    db: AsyncSession,
    *,
    query: Query,
    result: AgentQueryResult,
) -> None:
    if result.run_id == "":
        raise AppError("AGENT_RESPONSE_INVALID", "Agent run identifier is missing.", 502)

    document_ids = {
        citation.document_id
        for citation in result.citations
        if citation.document_id is not None
    }
    documents: dict[str, Document] = {}
    if document_ids:
        rows = list(
            (
                await db.scalars(
                    select(Document).where(Document.id.in_(document_ids))
                )
            ).all()
        )
        documents = {row.id: row for row in rows}

    for citation in result.citations:
        if not citation.access_allowed:
            raise AppError(
                "AGENT_EVIDENCE_FORBIDDEN",
                "Agent result contains evidence marked as inaccessible.",
                502,
            )
        if citation.document_id is None:
            continue
        document = documents.get(citation.document_id)
        if document is None:
            if settings.agent_gateway_mode == "mock" and settings.app_env.lower() not in {"production", "prod"}:
                continue
            raise AppError(
                "AGENT_EVIDENCE_INVALID",
                "Agent result references an unknown document.",
                502,
                details={"document_id": citation.document_id},
            )
        if (
            document.organisation_id != query.organisation_id
            or document.site_id != query.site_id
        ):
            raise AppError(
                "AGENT_EVIDENCE_FORBIDDEN",
                "Agent result references evidence outside the query scope.",
                502,
                details={"document_id": citation.document_id},
            )
        if (
            query.context_document_ids
            and citation.document_id not in query.context_document_ids
        ):
            raise AppError(
                "AGENT_EVIDENCE_OUT_OF_SCOPE",
                "Agent result references a document outside the requested scope.",
                502,
                details={"document_id": citation.document_id},
            )

        if citation.evidence_region_id:
            region = await db.get(EvidenceRegion, citation.evidence_region_id)
            if region is None or region.document_id != document.id:
                raise AppError(
                    "AGENT_EVIDENCE_INVALID",
                    "Evidence region does not belong to the cited document.",
                    502,
                    details={"evidence_region_id": citation.evidence_region_id},
                )
