from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models import AuditEvent


async def write_audit(
    db: AsyncSession,
    *,
    organisation_id: str,
    site_id: str | None,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    request_id: str | None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            organisation_id=organisation_id,
            site_id=site_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            metadata_json=metadata or {},
        )
    )
