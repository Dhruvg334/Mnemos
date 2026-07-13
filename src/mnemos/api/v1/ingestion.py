from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.config import settings
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Document, IngestionEvent, IngestionRun
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.ingestion import IngestionEventResponse, IngestionRunResponse
from mnemos.services.audit import write_audit
from mnemos.services.idempotency import (
    find_idempotent_resource,
    request_hash,
    save_idempotency_record,
    validate_idempotency_key,
)
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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    document = await db.get(Document, document_id)
    if document is None:
        raise AppError("NOT_FOUND", "Document not found.", 404)
    require_site_access(principal, document.site_id)
    if not document.storage_key:
        raise AppError("DOCUMENT_NOT_READY", "Document has no stored object.", 409)

    key = validate_idempotency_key(idempotency_key)
    payload_hash = request_hash({"document_id": document.id, "document_version": document.version})
    if key:
        existing = await find_idempotent_resource(
            db,
            user_id=principal.user.id,
            operation="document.ingest",
            key=key,
            payload_hash=payload_hash,
        )
        if existing is not None:
            previous = await db.get(IngestionRun, existing.resource_id)
            if previous is None:
                raise AppError(
                    "IDEMPOTENCY_RESOURCE_MISSING",
                    "The previous idempotent resource is unavailable.",
                    409,
                )
            return Envelope(
                data=IngestionRunResponse.model_validate(previous),
                meta=Meta(request_id=request.state.request_id),
            )

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
    if key:
        await save_idempotency_record(
            db,
            user_id=principal.user.id,
            organisation_id=document.organisation_id,
            site_id=document.site_id,
            operation="document.ingest",
            key=key,
            payload_hash=payload_hash,
            resource_type="ingestion_run",
            resource_id=run.id,
            response_status=202,
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


@router.post(
    "/runs/{run_id}/retry",
    response_model=Envelope[IngestionRunResponse],
    status_code=202,
)
async def retry_ingestion(
    run_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    previous = await db.get(IngestionRun, run_id)
    if previous is None:
        raise AppError("NOT_FOUND", "Ingestion run not found.", 404)
    require_site_access(principal, previous.site_id)
    if previous.status != "failed":
        raise AppError(
            "INVALID_STATE",
            "Only failed ingestion runs can be retried.",
            409,
            details={"current_status": previous.status},
        )

    attempts = list(
        (
            await db.scalars(
                select(IngestionRun).where(
                    IngestionRun.document_id == previous.document_id,
                    IngestionRun.document_version == previous.document_version,
                )
            )
        ).all()
    )
    if len(attempts) >= settings.ingestion_max_retry_attempts + 1:
        raise AppError(
            "RETRY_LIMIT_REACHED",
            "Ingestion retry limit reached.",
            409,
            details={"attempts": len(attempts)},
        )

    document = await db.get(Document, previous.document_id)
    if document is None:
        raise AppError("NOT_FOUND", "Document not found.", 404)

    run = await execute_ingestion(db, document=document)
    await write_audit(
        db,
        organisation_id=document.organisation_id,
        site_id=document.site_id,
        actor_id=principal.user.id,
        action="document.ingestion_retry_requested",
        resource_type="ingestion_run",
        resource_id=run.id,
        request_id=request.state.request_id,
        metadata={"previous_run_id": previous.id},
    )
    await db.commit()
    await db.refresh(run)
    return Envelope(
        data=IngestionRunResponse.model_validate(run),
        meta=Meta(request_id=request.state.request_id),
    )
