from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_admin, require_site_access
from mnemos.core.config import settings
from mnemos.core.db import get_db
from mnemos.models import AuditEvent
from mnemos.schemas.audit import AuditEventResponse, AuditPageResponse
from mnemos.schemas.common import Envelope, Meta

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=Envelope[AuditPageResponse])
async def list_audit_events(
    request: Request,
    site_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    require_admin(principal)
    limit = max(1, min(limit, settings.audit_page_size_max))

    conditions = []
    if site_id:
        require_site_access(principal, site_id)
        conditions.append(AuditEvent.site_id == site_id)
    else:
        organisation_ids = {m.organisation_id for m in principal.memberships}
        conditions.append(AuditEvent.organisation_id.in_(organisation_ids))

    if actor_id:
        conditions.append(AuditEvent.actor_id == actor_id)
    if action:
        conditions.append(AuditEvent.action == action)
    if resource_type:
        conditions.append(AuditEvent.resource_type == resource_type)
    if cursor:
        cursor_time, cursor_id = cursor.split("|", 1)
        parsed = datetime.fromisoformat(cursor_time)
        conditions.append(
            or_(
                AuditEvent.occurred_at < parsed,
                and_(
                    AuditEvent.occurred_at == parsed,
                    AuditEvent.id < cursor_id,
                ),
            )
        )

    rows = list(
        (
            await db.scalars(
                select(AuditEvent)
                .where(*conditions)
                .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
                .limit(limit + 1)
            )
        ).all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = f"{last.occurred_at.isoformat()}|{last.id}"

    items = [
        AuditEventResponse(
            id=row.id,
            organisation_id=row.organisation_id,
            site_id=row.site_id,
            actor_id=row.actor_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            request_id=row.request_id,
            metadata=dict(row.metadata_json or {}),
            occurred_at=row.occurred_at,
        )
        for row in rows
    ]
    return Envelope(
        data=AuditPageResponse(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
        ),
        meta=Meta(request_id=request.state.request_id),
    )
