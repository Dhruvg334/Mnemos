from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_site_access, require_site_role
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Asset, RCAAction, RCACase, RCAHypothesis, RCAObservation, Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.rca import (
    RCAActionCreate, RCAActionResponse, RCACreate, RCAHypothesisCreate,
    RCAHypothesisResponse, RCAObservationCreate, RCAObservationResponse,
    RCAResponse, RCAReviewRequest, RCAUpdate,
)
from mnemos.services.audit import write_audit
from mnemos.services.rca import load_rca_bundle, rca_snapshot

router = APIRouter(prefix="/rcas", tags=["rca"])
WRITE_ROLES = {"platform_admin", "organisation_admin", "site_admin", "engineer", "maintenance_user", "safety_user"}
APPROVE_ROLES = {"platform_admin", "organisation_admin", "site_admin", "safety_user"}


def _serialize(bundle: dict) -> RCAResponse:
    rca = bundle["rca"]
    data = RCAResponse.model_validate(rca)
    data.observations = [RCAObservationResponse.model_validate(x) for x in bundle["observations"]]
    data.hypotheses = [RCAHypothesisResponse.model_validate(x) for x in bundle["hypotheses"]]
    data.actions = [RCAActionResponse.model_validate(x) for x in bundle["actions"]]
    return data


async def _get_rca(db: AsyncSession, rca_id: str, principal: Principal) -> RCACase:
    rca = await db.get(RCACase, rca_id)
    if rca is None:
        raise AppError("NOT_FOUND", "RCA not found.", 404)
    require_site_access(principal, rca.site_id)
    return rca


@router.post("", response_model=Envelope[RCAResponse], status_code=201)
async def create_rca(payload: RCACreate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    require_site_role(principal, payload.site_id, WRITE_ROLES)
    site = await db.get(Site, payload.site_id)
    asset = await db.get(Asset, payload.asset_id)
    if site is None or asset is None or asset.site_id != site.id:
        raise AppError("VALIDATION_ERROR", "Asset does not belong to the selected site.", 422)
    rca = RCACase(organisation_id=site.organisation_id, site_id=site.id, asset_id=asset.id, title=payload.title, problem_statement=payload.problem_statement, severity=payload.severity, created_by=principal.user.id)
    db.add(rca)
    await db.flush()
    await write_audit(db, organisation_id=site.organisation_id, site_id=site.id, actor_id=principal.user.id, action="rca.created", resource_type="rca", resource_id=rca.id, request_id=request.state.request_id)
    await db.commit()
    return Envelope(data=_serialize(await load_rca_bundle(db, rca)), meta=Meta(request_id=request.state.request_id))


@router.get("", response_model=Envelope[list[RCAResponse]])
async def list_rcas(request: Request, site_id: str, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    require_site_access(principal, site_id)
    rows = list((await db.scalars(select(RCACase).where(RCACase.site_id == site_id).order_by(RCACase.created_at.desc()))).all())
    data = [_serialize(await load_rca_bundle(db, item)) for item in rows]
    return Envelope(data=data, meta=Meta(request_id=request.state.request_id))


@router.get("/{rca_id}", response_model=Envelope[RCAResponse])
async def get_rca(rca_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal)
    return Envelope(data=_serialize(await load_rca_bundle(db, rca)), meta=Meta(request_id=request.state.request_id))


@router.patch("/{rca_id}", response_model=Envelope[RCAResponse])
async def update_rca(rca_id: str, payload: RCAUpdate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal)
    require_site_role(principal, rca.site_id, WRITE_ROLES)
    if rca.status != "draft":
        raise AppError("CONFLICT", "Only draft RCAs can be edited.", 409)
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(rca, field, value)
    await db.commit()
    return Envelope(data=_serialize(await load_rca_bundle(db, rca)), meta=Meta(request_id=request.state.request_id))


@router.post("/{rca_id}/observations", response_model=Envelope[RCAObservationResponse], status_code=201)
async def add_observation(rca_id: str, payload: RCAObservationCreate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal); require_site_role(principal, rca.site_id, WRITE_ROLES)
    if rca.status != "draft": raise AppError("CONFLICT", "Only draft RCAs can be changed.", 409)
    row = RCAObservation(rca_id=rca.id, **payload.model_dump()); db.add(row); await db.commit(); await db.refresh(row)
    return Envelope(data=RCAObservationResponse.model_validate(row), meta=Meta(request_id=request.state.request_id))


@router.post("/{rca_id}/hypotheses", response_model=Envelope[RCAHypothesisResponse], status_code=201)
async def add_hypothesis(rca_id: str, payload: RCAHypothesisCreate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal); require_site_role(principal, rca.site_id, WRITE_ROLES)
    if rca.status != "draft": raise AppError("CONFLICT", "Only draft RCAs can be changed.", 409)
    row = RCAHypothesis(rca_id=rca.id, **payload.model_dump()); db.add(row); await db.commit(); await db.refresh(row)
    return Envelope(data=RCAHypothesisResponse.model_validate(row), meta=Meta(request_id=request.state.request_id))


@router.post("/{rca_id}/actions", response_model=Envelope[RCAActionResponse], status_code=201)
async def add_action(rca_id: str, payload: RCAActionCreate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal); require_site_role(principal, rca.site_id, WRITE_ROLES)
    if rca.status != "draft": raise AppError("CONFLICT", "Only draft RCAs can be changed.", 409)
    row = RCAAction(rca_id=rca.id, **payload.model_dump()); db.add(row); await db.commit(); await db.refresh(row)
    return Envelope(data=RCAActionResponse.model_validate(row), meta=Meta(request_id=request.state.request_id))


@router.post("/{rca_id}/submit", response_model=Envelope[RCAResponse])
async def submit_rca(rca_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal); require_site_role(principal, rca.site_id, WRITE_ROLES)
    if rca.status != "draft": raise AppError("CONFLICT", "Only draft RCAs can be submitted.", 409)
    bundle = await load_rca_bundle(db, rca)
    if not bundle["observations"] or not bundle["hypotheses"]:
        raise AppError("VALIDATION_ERROR", "RCA requires at least one observation and one hypothesis.", 422)
    rca.status = "under_review"; rca.submitted_by = principal.user.id; rca.submitted_at = datetime.now(UTC)
    await db.commit()
    return Envelope(data=_serialize(await load_rca_bundle(db, rca)), meta=Meta(request_id=request.state.request_id))


@router.post("/{rca_id}/approve", response_model=Envelope[RCAResponse])
async def approve_rca(rca_id: str, payload: RCAReviewRequest, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal); require_site_role(principal, rca.site_id, APPROVE_ROLES)
    if rca.status != "under_review": raise AppError("CONFLICT", "RCA is not awaiting review.", 409)
    bundle = await load_rca_bundle(db, rca); rca.status = "approved"; rca.approved_by = principal.user.id; rca.approved_at = datetime.now(UTC); rca.review_note = payload.note; rca.approved_snapshot = rca_snapshot(bundle)
    await db.commit()
    return Envelope(data=_serialize(await load_rca_bundle(db, rca)), meta=Meta(request_id=request.state.request_id))


@router.post("/{rca_id}/reject", response_model=Envelope[RCAResponse])
async def reject_rca(rca_id: str, payload: RCAReviewRequest, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    rca = await _get_rca(db, rca_id, principal); require_site_role(principal, rca.site_id, APPROVE_ROLES)
    if rca.status != "under_review": raise AppError("CONFLICT", "RCA is not awaiting review.", 409)
    rca.status = "rejected"; rca.rejected_by = principal.user.id; rca.review_note = payload.note
    await db.commit()
    return Envelope(data=_serialize(await load_rca_bundle(db, rca)), meta=Meta(request_id=request.state.request_id))
