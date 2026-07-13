from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Asset
from mnemos.schemas.asset import (
    AssetAliasResponse,
    AssetGraphResponse,
    AssetResponse,
    AssetTimelineResponse,
)
from mnemos.services.assets import build_asset_graph, build_asset_timeline, list_asset_aliases
from mnemos.schemas.common import Envelope, Meta

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=Envelope[list[AssetResponse]])
async def list_assets(
    request: Request,
    site_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[list[AssetResponse]]:
    require_site_access(principal, site_id)
    assets = list((await db.scalars(select(Asset).where(Asset.site_id == site_id))).all())
    return Envelope(
        data=[AssetResponse.model_validate(asset) for asset in assets],
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("/{asset_id}", response_model=Envelope[AssetResponse])
async def get_asset(
    asset_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[AssetResponse]:
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise AppError("NOT_FOUND", "Asset not found.", 404)
    require_site_access(principal, asset.site_id)
    return Envelope(
        data=AssetResponse.model_validate(asset),
        meta=Meta(request_id=request.state.request_id),
    )



@router.get("/{asset_id}/timeline", response_model=Envelope[AssetTimelineResponse])
async def get_asset_timeline(
    asset_id: str,
    request: Request,
    limit: int = 100,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise AppError("NOT_FOUND", "Asset not found.", 404)
    require_site_access(principal, asset.site_id)
    result = await build_asset_timeline(db, asset=asset, limit=max(1, min(limit, 250)))
    return Envelope(data=result, meta=Meta(request_id=request.state.request_id))


@router.get("/{asset_id}/graph", response_model=Envelope[AssetGraphResponse])
async def get_asset_graph(
    asset_id: str,
    request: Request,
    max_depth: int = 2,
    max_edges: int = 100,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise AppError("NOT_FOUND", "Asset not found.", 404)
    require_site_access(principal, asset.site_id)
    result = await build_asset_graph(
        db,
        asset=asset,
        max_depth=max(1, min(max_depth, 3)),
        max_edges=max(1, min(max_edges, 250)),
    )
    return Envelope(data=result, meta=Meta(request_id=request.state.request_id))


@router.get("/{asset_id}/aliases", response_model=Envelope[list[AssetAliasResponse]])
async def get_asset_aliases(
    asset_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise AppError("NOT_FOUND", "Asset not found.", 404)
    require_site_access(principal, asset.site_id)
    rows = await list_asset_aliases(db, asset_id=asset.id)
    return Envelope(
        data=[AssetAliasResponse.model_validate(row) for row in rows],
        meta=Meta(request_id=request.state.request_id),
    )
