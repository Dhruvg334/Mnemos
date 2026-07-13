from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_site_access, require_site_role
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Asset, KnowledgeCard, Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.knowledge import KnowledgeCardCreate, KnowledgeCardResponse, KnowledgeCardUpdate, KnowledgeReviewRequest
from mnemos.services.audit import write_audit

router = APIRouter(prefix="/knowledge-cards", tags=["knowledge-cards"])
WRITE_ROLES = {"platform_admin", "organisation_admin", "site_admin", "engineer", "maintenance_user", "safety_user", "quality_user"}
REVIEW_ROLES = {"platform_admin", "organisation_admin", "site_admin", "engineer", "safety_user", "quality_user"}


async def _get_card(db: AsyncSession, card_id: str, principal: Principal) -> KnowledgeCard:
    card = await db.get(KnowledgeCard, card_id)
    if card is None: raise AppError("NOT_FOUND", "Knowledge card not found.", 404)
    require_site_access(principal, card.site_id)
    return card


@router.post("", response_model=Envelope[KnowledgeCardResponse], status_code=201)
async def create_card(payload: KnowledgeCardCreate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    require_site_role(principal, payload.site_id, WRITE_ROLES)
    site = await db.get(Site, payload.site_id)
    if site is None: raise AppError("NOT_FOUND", "Site not found.", 404)
    if payload.asset_id:
        asset = await db.get(Asset, payload.asset_id)
        if asset is None or asset.site_id != site.id: raise AppError("VALIDATION_ERROR", "Asset does not belong to the selected site.", 422)
    if payload.supersedes_id:
        old = await db.get(KnowledgeCard, payload.supersedes_id)
        if old is None or old.site_id != site.id or old.status != "approved": raise AppError("VALIDATION_ERROR", "Only an approved card in the same site can be superseded.", 422)
    card = KnowledgeCard(organisation_id=site.organisation_id, site_id=site.id, asset_id=payload.asset_id, title=payload.title, content=payload.content, author_id=principal.user.id, supersedes_id=payload.supersedes_id)
    db.add(card); await db.flush()
    await write_audit(db, organisation_id=site.organisation_id, site_id=site.id, actor_id=principal.user.id, action="knowledge_card.created", resource_type="knowledge_card", resource_id=card.id, request_id=request.state.request_id)
    await db.commit(); await db.refresh(card)
    return Envelope(data=KnowledgeCardResponse.model_validate(card), meta=Meta(request_id=request.state.request_id))


@router.get("", response_model=Envelope[list[KnowledgeCardResponse]])
async def list_cards(request: Request, site_id: str, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    require_site_access(principal, site_id)
    rows = list((await db.scalars(select(KnowledgeCard).where(KnowledgeCard.site_id == site_id).order_by(KnowledgeCard.updated_at.desc()))).all())
    return Envelope(data=[KnowledgeCardResponse.model_validate(x) for x in rows], meta=Meta(request_id=request.state.request_id))


@router.get("/{card_id}", response_model=Envelope[KnowledgeCardResponse])
async def get_card(card_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    card = await _get_card(db, card_id, principal)
    return Envelope(data=KnowledgeCardResponse.model_validate(card), meta=Meta(request_id=request.state.request_id))


@router.patch("/{card_id}", response_model=Envelope[KnowledgeCardResponse])
async def update_card(card_id: str, payload: KnowledgeCardUpdate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    card = await _get_card(db, card_id, principal); require_site_role(principal, card.site_id, WRITE_ROLES)
    if card.status != "draft": raise AppError("CONFLICT", "Only draft knowledge cards can be edited.", 409)
    if card.author_id != principal.user.id and not any(m.role in {"platform_admin", "organisation_admin", "site_admin"} for m in principal.memberships): raise AppError("FORBIDDEN", "Only the author or an administrator can edit this card.", 403)
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(card, field, value)
    card.version += 1
    await db.commit(); await db.refresh(card)
    return Envelope(data=KnowledgeCardResponse.model_validate(card), meta=Meta(request_id=request.state.request_id))


@router.post("/{card_id}/submit", response_model=Envelope[KnowledgeCardResponse])
async def submit_card(card_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    card = await _get_card(db, card_id, principal); require_site_role(principal, card.site_id, WRITE_ROLES)
    if card.status != "draft": raise AppError("CONFLICT", "Only draft knowledge cards can be submitted.", 409)
    card.status = "pending_review"; card.submitted_at = datetime.now(UTC)
    await db.commit(); await db.refresh(card)
    return Envelope(data=KnowledgeCardResponse.model_validate(card), meta=Meta(request_id=request.state.request_id))


@router.post("/{card_id}/approve", response_model=Envelope[KnowledgeCardResponse])
async def approve_card(card_id: str, payload: KnowledgeReviewRequest, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    card = await _get_card(db, card_id, principal); require_site_role(principal, card.site_id, REVIEW_ROLES)
    if card.status != "pending_review": raise AppError("CONFLICT", "Knowledge card is not awaiting review.", 409)
    if card.author_id == principal.user.id: raise AppError("FORBIDDEN", "Authors cannot approve their own knowledge cards.", 403)
    card.status = "approved"; card.reviewer_id = principal.user.id; card.review_note = payload.note; card.reviewed_at = datetime.now(UTC)
    if card.supersedes_id:
        old = await db.get(KnowledgeCard, card.supersedes_id)
        if old: old.status = "superseded"
    await db.commit(); await db.refresh(card)
    return Envelope(data=KnowledgeCardResponse.model_validate(card), meta=Meta(request_id=request.state.request_id))


@router.post("/{card_id}/reject", response_model=Envelope[KnowledgeCardResponse])
async def reject_card(card_id: str, payload: KnowledgeReviewRequest, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    card = await _get_card(db, card_id, principal); require_site_role(principal, card.site_id, REVIEW_ROLES)
    if card.status != "pending_review": raise AppError("CONFLICT", "Knowledge card is not awaiting review.", 409)
    if card.author_id == principal.user.id: raise AppError("FORBIDDEN", "Authors cannot review their own knowledge cards.", 403)
    card.status = "rejected"; card.reviewer_id = principal.user.id; card.review_note = payload.note; card.reviewed_at = datetime.now(UTC)
    await db.commit(); await db.refresh(card)
    return Envelope(data=KnowledgeCardResponse.model_validate(card), meta=Meta(request_id=request.state.request_id))
