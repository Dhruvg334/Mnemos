from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.config import settings
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Asset, Document, Query, QueryEvent, Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.query import QueryAccepted, QueryCreate, QueryEventResponse, QueryResponse
from mnemos.services.audit import write_audit
from mnemos.services.idempotency import (
    find_idempotent_resource,
    request_hash,
    save_idempotency_record,
    validate_idempotency_key,
)
from mnemos.services.query_execution import add_query_event, execute_query_background

router = APIRouter(prefix="/queries", tags=["queries"])


@router.post("", response_model=Envelope[QueryAccepted], status_code=202)
async def create_query(
    payload: QueryCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[QueryAccepted]:
    membership = require_site_access(principal, payload.site_id)
    site = await db.get(Site, payload.site_id)
    if site is None:
        raise AppError("NOT_FOUND", "Site not found.", 404)

    if len(set(payload.context.asset_ids)) != len(payload.context.asset_ids):
        raise AppError("VALIDATION_ERROR", "Duplicate asset IDs are not allowed.", 422)
    if len(set(payload.context.document_ids)) != len(payload.context.document_ids):
        raise AppError("VALIDATION_ERROR", "Duplicate document IDs are not allowed.", 422)

    if payload.context.asset_ids:
        assets = list(
            (await db.scalars(select(Asset).where(Asset.id.in_(payload.context.asset_ids)))).all()
        )
        if len(assets) != len(payload.context.asset_ids) or any(
            asset.site_id != site.id for asset in assets
        ):
            raise AppError(
                "VALIDATION_ERROR", "One or more assets are outside the selected site.", 422
            )

    if payload.context.document_ids:
        documents = list(
            (
                await db.scalars(
                    select(Document).where(Document.id.in_(payload.context.document_ids))
                )
            ).all()
        )
        if len(documents) != len(payload.context.document_ids) or any(
            document.site_id != site.id for document in documents
        ):
            raise AppError(
                "VALIDATION_ERROR", "One or more documents are outside the selected site.", 422
            )

    key = validate_idempotency_key(idempotency_key)
    payload_hash = request_hash(payload.model_dump(mode="json"))
    if key:
        existing = await find_idempotent_resource(
            db,
            user_id=principal.user.id,
            operation="query.create",
            key=key,
            payload_hash=payload_hash,
        )
        if existing is not None:
            previous = await db.get(Query, existing.resource_id)
            if previous is None:
                raise AppError(
                    "IDEMPOTENCY_RESOURCE_MISSING",
                    "The previous idempotent resource is unavailable.",
                    409,
                )
            return Envelope(
                data=QueryAccepted(
                    id=previous.id,
                    status=previous.status,
                    created_at=previous.created_at,
                ),
                meta=Meta(request_id=request.state.request_id),
            )

    query = Query(
        organisation_id=site.organisation_id,
        site_id=site.id,
        user_id=principal.user.id,
        question=payload.question,
        mode=payload.mode,
        context_asset_ids=list(payload.context.asset_ids),
        context_document_ids=list(payload.context.document_ids),
        status="queued",
    )
    db.add(query)
    await db.flush()
    await add_query_event(
        db,
        query_id=query.id,
        stage="queued",
        progress_percent=0,
        message="Query queued",
    )
    await write_audit(
        db,
        organisation_id=site.organisation_id,
        site_id=site.id,
        actor_id=principal.user.id,
        action="query.created",
        resource_type="query",
        resource_id=query.id,
        request_id=request.state.request_id,
        metadata={"mode": payload.mode, "role": membership.role},
    )
    if key:
        await save_idempotency_record(
            db,
            user_id=principal.user.id,
            organisation_id=site.organisation_id,
            site_id=site.id,
            operation="query.create",
            key=key,
            payload_hash=payload_hash,
            resource_type="query",
            resource_id=query.id,
            response_status=202,
        )
    await db.commit()
    await db.refresh(query)

    background_tasks.add_task(execute_query_background, query.id)
    return Envelope(
        data=QueryAccepted(id=query.id, status=query.status, created_at=query.created_at),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("/{query_id}", response_model=Envelope[QueryResponse])
async def get_query(
    query_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[QueryResponse]:
    query = await db.scalar(
        select(Query)
        .options(
            selectinload(Query.claims),
            selectinload(Query.citations),
            selectinload(Query.agent_runs),
        )
        .where(Query.id == query_id)
    )
    if query is None:
        raise AppError("NOT_FOUND", "Query not found.", 404)
    require_site_access(principal, query.site_id)
    return Envelope(
        data=QueryResponse.model_validate(query),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("/{query_id}/events", response_model=Envelope[list[QueryEventResponse]])
async def list_query_events(
    query_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[list[QueryEventResponse]]:
    query = await db.get(Query, query_id)
    if query is None:
        raise AppError("NOT_FOUND", "Query not found.", 404)
    require_site_access(principal, query.site_id)
    events = list(
        (
            await db.scalars(
                select(QueryEvent)
                .where(QueryEvent.query_id == query_id)
                .order_by(QueryEvent.created_at)
            )
        ).all()
    )
    return Envelope(
        data=[QueryEventResponse.model_validate(event) for event in events],
        meta=Meta(request_id=request.state.request_id),
    )


@router.post("/{query_id}/cancel", response_model=Envelope[QueryAccepted])
async def cancel_query(
    query_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[QueryAccepted]:
    query = await db.scalar(select(Query).where(Query.id == query_id).with_for_update())
    if query is None:
        raise AppError("NOT_FOUND", "Query not found.", 404)
    membership = require_site_access(principal, query.site_id)
    if query.user_id != principal.user.id and membership.role not in {
        "platform_admin",
        "organisation_admin",
        "site_admin",
    }:
        raise AppError("FORBIDDEN", "Only the query owner or an administrator may cancel it.", 403)
    if query.status not in {"queued", "running"}:
        raise AppError(
            "INVALID_STATE",
            "Only queued or running queries can be cancelled.",
            409,
            details={"current_status": query.status},
        )

    query.status = "cancelled"
    query.completed_at = datetime.now(UTC)
    await add_query_event(
        db,
        query_id=query.id,
        stage="cancelled",
        progress_percent=100,
        message="Query cancelled",
    )
    await write_audit(
        db,
        organisation_id=query.organisation_id,
        site_id=query.site_id,
        actor_id=principal.user.id,
        action="query.cancelled",
        resource_type="query",
        resource_id=query.id,
        request_id=request.state.request_id,
        metadata={},
    )
    await db.commit()
    await db.refresh(query)
    return Envelope(
        data=QueryAccepted(id=query.id, status=query.status, created_at=query.created_at),
        meta=Meta(request_id=request.state.request_id),
    )


@router.post("/{query_id}/retry", response_model=Envelope[QueryAccepted], status_code=202)
async def retry_query(
    query_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[QueryAccepted]:
    query = await db.scalar(select(Query).where(Query.id == query_id).with_for_update())
    if query is None:
        raise AppError("NOT_FOUND", "Query not found.", 404)
    membership = require_site_access(principal, query.site_id)
    if query.user_id != principal.user.id and membership.role not in {
        "platform_admin",
        "organisation_admin",
        "site_admin",
    }:
        raise AppError("FORBIDDEN", "Only the query owner or an administrator may retry it.", 403)
    if query.status not in {"failed", "cancelled"}:
        raise AppError(
            "INVALID_STATE",
            "Only failed or cancelled queries can be retried.",
            409,
            details={"current_status": query.status},
        )

    prior_attempts = len(query.agent_runs)
    if prior_attempts >= settings.query_max_retry_attempts + 1:
        raise AppError(
            "RETRY_LIMIT_REACHED",
            "Query retry limit reached.",
            409,
            details={"attempts": prior_attempts},
        )

    query.status = "queued"
    query.completed_at = None
    await add_query_event(
        db,
        query_id=query.id,
        stage="queued",
        progress_percent=0,
        message="Query queued for retry",
    )
    await write_audit(
        db,
        organisation_id=query.organisation_id,
        site_id=query.site_id,
        actor_id=principal.user.id,
        action="query.retry_requested",
        resource_type="query",
        resource_id=query.id,
        request_id=request.state.request_id,
        metadata={"previous_attempts": prior_attempts},
    )
    await db.commit()
    await db.refresh(query)
    background_tasks.add_task(execute_query_background, query.id)
    return Envelope(
        data=QueryAccepted(id=query.id, status=query.status, created_at=query.created_at),
        meta=Meta(request_id=request.state.request_id),
    )
