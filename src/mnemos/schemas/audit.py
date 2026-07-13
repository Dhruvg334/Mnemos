from datetime import datetime

from mnemos.schemas.common import APIModel


class AuditEventResponse(APIModel):
    id: str
    organisation_id: str
    site_id: str | None
    actor_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    request_id: str | None
    metadata: dict
    occurred_at: datetime


class AuditPageResponse(APIModel):
    items: list[AuditEventResponse]
    next_cursor: str | None
    has_more: bool
