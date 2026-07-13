from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Query, QueryEvent, Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.query import QueryAccepted, QueryCreate, QueryEventResponse, QueryResponse
from mnemos.services.audit import write_audit
from mnemos.services.query_execution import add_query_event, execute_query_background

router = APIRouter(prefix="/queries", tags=["queries"])


@router.post("", response_model=Envelope[QueryAccepted], status_code=202)
async def create_query(
    payload: QueryCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[QueryAccepted]:
    membership = require_site_access(principal, payload.site_id)
    site = await db.get(Site, payload.site_id)
    if site is None:
        raise AppError("NOT_FOUND", "Site not found.", 404)

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
