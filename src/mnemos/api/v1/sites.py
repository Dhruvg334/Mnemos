from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal
from mnemos.core.db import get_db
from mnemos.models import Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.site import SiteResponse

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=Envelope[list[SiteResponse]])
async def list_sites(
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[list[SiteResponse]]:
    unrestricted_orgs = {m.organisation_id for m in principal.memberships if m.site_id is None}
    site_ids = {m.site_id for m in principal.memberships if m.site_id is not None}

    conditions = []
    if unrestricted_orgs:
        conditions.append(Site.organisation_id.in_(unrestricted_orgs))
    if site_ids:
        conditions.append(Site.id.in_(site_ids))

    if not conditions:
        sites = []
    else:
        from sqlalchemy import or_

        sites = list((await db.scalars(select(Site).where(or_(*conditions)))).all())

    return Envelope(
        data=[SiteResponse.model_validate(site) for site in sites],
        meta=Meta(request_id=request.state.request_id),
    )
