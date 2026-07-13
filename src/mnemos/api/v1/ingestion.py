from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Document, IngestionEvent, IngestionRun
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.ingestion import IngestionEventResponse, IngestionRunResponse
from mnemos.services.audit import write_audit
from mnemos.services.ingestion_execution import execute_ingestion

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post(
    "/documents/{document_id}",
    response_model=Envelope[IngestionRunResponse],
    status_code=202,
)
async def ingest_document(
    document_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if document is None:
        raise AppError("NOT_FOUND", "Document not found.", 404)
    require_site_access(principal, document.site_id)
    if not document.storage_key:
        raise AppError("DOCUMENT_NOT_READY", "Document has no stored object.", 409)

    running = await db.scalar(
        select(IngestionRun).where(
            IngestionRun.document_id == document.id,
            IngestionRun.status.in_(["queued", "running"]),
        )
    )
    if running is not None:
        raise AppError(
            "CONFLICT",
            "Document ingestion is already in progress.",
            409,
            details={"ingestion_run_id": running.id},
        )

    run = await execute_ingestion(db, document=document)
    await write_audit(
        db,
        organisation_id=document.organisation_id,
        site_id=document.site_id,
        actor_id=principal.user.id,
        action="document.ingestion_started",
        resource_type="ingestion_run",
        resource_id=run.id,
        request_id=request.state.request_id,
        metadata={"document_id": document.id, "gateway": run.gateway},
    )
    await db.commit()
    await db.refresh(run)
    return Envelope(
        data=IngestionRunResponse.model_validate(run),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get(
    "/runs/{run_id}",
    response_model=Envelope[IngestionRunResponse],
)
async def get_ingestion_run(
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(IngestionRun, run_id)
    if run is None:
        raise AppError("NOT_FOUND", "Ingestion run not found.", 404)
    require_site_access(principal, run.site_id)
    return Envelope(
        data=IngestionRunResponse.model_validate(run),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get(
    "/runs/{run_id}/events",
    response_model=Envelope[list[IngestionEventResponse]],
)
async def get_ingestion_events(
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(IngestionRun, run_id)
    if run is None:
        raise AppError("NOT_FOUND", "Ingestion run not found.", 404)
    require_site_access(principal, run.site_id)
    rows = list(
        (
            await db.scalars(
                select(IngestionEvent)
                .where(IngestionEvent.ingestion_run_id == run.id)
                .order_by(IngestionEvent.created_at)
            )
        ).all()
    )
    return Envelope(
        data=[IngestionEventResponse.model_validate(item) for item in rows],
        meta=Meta(request_id=request.state.request_id),
    )
