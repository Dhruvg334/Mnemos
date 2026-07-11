from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Citation, Query, Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.query import QueryCreate, QueryResponse
from mnemos.services.audit import write_audit
from mnemos.services.mock_agent import MockAgentGateway

router = APIRouter(prefix="/queries", tags=["queries"])
agent_gateway = MockAgentGateway()


@router.post("", response_model=Envelope[QueryResponse], status_code=201)
async def create_query(
    payload: QueryCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[QueryResponse]:
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
        status="running",
    )
    db.add(query)
    await db.flush()

    result = await agent_gateway.execute_query(payload.question)
    query.answer = result.answer
    query.confidence_label = result.confidence_label
    query.confidence_score = result.confidence_score
    query.missing_evidence = result.missing_evidence
    query.conflicts = result.conflicts
    query.related_entities = result.related_entities
    query.status = "partially_succeeded" if result.partial else "succeeded"
    query.completed_at = datetime.now(UTC)

    for item in result.citations:
        db.add(
            Citation(
                query_id=query.id,
                claim_text=item.claim_text,
                support_status=item.support_status,
                document_title=item.document_title,
                page_or_sheet=item.page_or_sheet,
                locator=item.locator,
                text_excerpt=item.text_excerpt,
                access_allowed=item.access_allowed,
            )
        )

    await write_audit(
        db,
        organisation_id=site.organisation_id,
        site_id=site.id,
        actor_id=principal.user.id,
        action="query.executed",
        resource_type="query",
        resource_id=query.id,
        request_id=request.state.request_id,
        metadata={"mode": payload.mode, "role": membership.role},
    )
    await db.commit()

    query = await db.scalar(
        select(Query).options(selectinload(Query.citations)).where(Query.id == query.id)
    )
    assert query is not None
    return Envelope(
        data=QueryResponse.model_validate(query),
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
        select(Query).options(selectinload(Query.citations)).where(Query.id == query_id)
    )
    if query is None:
        raise AppError("NOT_FOUND", "Query not found.", 404)
    require_site_access(principal, query.site_id)
    return Envelope(
        data=QueryResponse.model_validate(query),
        meta=Meta(request_id=request.state.request_id),
    )
