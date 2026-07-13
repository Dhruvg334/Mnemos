from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_site_access, require_site_role
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Asset, ComplianceEvaluation, ComplianceRequirement, Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.compliance import (
    ComplianceEvaluationCreate,
    ComplianceEvaluationResponse,
    ComplianceReviewRequest,
    RequirementCreate,
    RequirementResponse,
)
from mnemos.services.audit import write_audit

router = APIRouter(prefix="/compliance", tags=["compliance"])
RUN_ROLES = {
    "platform_admin",
    "organisation_admin",
    "site_admin",
    "engineer",
    "safety_user",
    "quality_user",
}
REVIEW_ROLES = {"platform_admin", "organisation_admin", "site_admin", "safety_user", "quality_user"}


@router.post("/requirements", response_model=Envelope[RequirementResponse], status_code=201)
async def create_requirement(
    payload: RequirementCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    memberships = [
        m
        for m in principal.memberships
        if m.organisation_id == payload.organisation_id
        and m.role in {"platform_admin", "organisation_admin"}
    ]
    if not memberships:
        raise AppError("FORBIDDEN", "Organisation administration permission required.", 403)
    existing = await db.scalar(
        select(ComplianceRequirement).where(
            ComplianceRequirement.organisation_id == payload.organisation_id,
            ComplianceRequirement.code == payload.code,
        )
    )
    if existing:
        raise AppError("CONFLICT", "Requirement code already exists.", 409)
    row = ComplianceRequirement(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return Envelope(
        data=RequirementResponse.model_validate(row), meta=Meta(request_id=request.state.request_id)
    )


@router.get("/requirements", response_model=Envelope[list[RequirementResponse]])
async def list_requirements(
    request: Request,
    organisation_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    if not any(m.organisation_id == organisation_id for m in principal.memberships):
        raise AppError("FORBIDDEN", "Organisation access denied.", 403)
    rows = list(
        (
            await db.scalars(
                select(ComplianceRequirement)
                .where(
                    ComplianceRequirement.organisation_id == organisation_id,
                    ComplianceRequirement.status == "active",
                )
                .order_by(ComplianceRequirement.code)
            )
        ).all()
    )
    return Envelope(
        data=[RequirementResponse.model_validate(x) for x in rows],
        meta=Meta(request_id=request.state.request_id),
    )


@router.post("/evaluations", response_model=Envelope[ComplianceEvaluationResponse], status_code=201)
async def create_evaluation(
    payload: ComplianceEvaluationCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    require_site_role(principal, payload.site_id, RUN_ROLES)
    site = await db.get(Site, payload.site_id)
    asset = await db.get(Asset, payload.asset_id)
    if site is None or asset is None or asset.site_id != site.id:
        raise AppError("VALIDATION_ERROR", "Asset does not belong to the selected site.", 422)
    requirements = list(
        (
            await db.scalars(
                select(ComplianceRequirement).where(
                    ComplianceRequirement.id.in_(payload.requirement_ids),
                    ComplianceRequirement.organisation_id == site.organisation_id,
                )
            )
        ).all()
    )
    if len(requirements) != len(set(payload.requirement_ids)):
        raise AppError(
            "VALIDATION_ERROR", "One or more requirements are invalid for this organisation.", 422
        )
    findings = [
        {
            "requirement_id": r.id,
            "result": "insufficient_evidence",
            "summary": "Evaluation awaits agent evidence mapping.",
            "evidence_region_ids": [],
        }
        for r in requirements
    ]
    row = ComplianceEvaluation(
        organisation_id=site.organisation_id,
        site_id=site.id,
        asset_id=asset.id,
        requirement_ids=list(payload.requirement_ids),
        status="partially_succeeded",
        overall_result="insufficient_evidence",
        findings=findings,
        missing_evidence=["Agent-derived compliance evidence"],
        created_by=principal.user.id,
        completed_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    await write_audit(
        db,
        organisation_id=site.organisation_id,
        site_id=site.id,
        actor_id=principal.user.id,
        action="compliance.evaluation_created",
        resource_type="compliance_evaluation",
        resource_id=row.id,
        request_id=request.state.request_id,
    )
    await db.commit()
    await db.refresh(row)
    return Envelope(
        data=ComplianceEvaluationResponse.model_validate(row),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("/evaluations/{evaluation_id}", response_model=Envelope[ComplianceEvaluationResponse])
async def get_evaluation(
    evaluation_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(ComplianceEvaluation, evaluation_id)
    if row is None:
        raise AppError("NOT_FOUND", "Compliance evaluation not found.", 404)
    require_site_access(principal, row.site_id)
    return Envelope(
        data=ComplianceEvaluationResponse.model_validate(row),
        meta=Meta(request_id=request.state.request_id),
    )


@router.post(
    "/evaluations/{evaluation_id}/review", response_model=Envelope[ComplianceEvaluationResponse]
)
async def review_evaluation(
    evaluation_id: str,
    payload: ComplianceReviewRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(ComplianceEvaluation, evaluation_id)
    if row is None:
        raise AppError("NOT_FOUND", "Compliance evaluation not found.", 404)
    require_site_role(principal, row.site_id, REVIEW_ROLES)
    if row.status not in {"succeeded", "partially_succeeded"}:
        raise AppError("CONFLICT", "Evaluation is not ready for review.", 409)
    row.status = "reviewed"
    row.reviewed_by = principal.user.id
    row.review_note = payload.note
    row.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return Envelope(
        data=ComplianceEvaluationResponse.model_validate(row),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("/assets/{asset_id}", response_model=Envelope[list[ComplianceEvaluationResponse]])
async def list_asset_evaluations(
    asset_id: str,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    asset = await db.get(Asset, asset_id)
    if asset is None:
        raise AppError("NOT_FOUND", "Asset not found.", 404)
    require_site_access(principal, asset.site_id)
    rows = list(
        (
            await db.scalars(
                select(ComplianceEvaluation)
                .where(ComplianceEvaluation.asset_id == asset.id)
                .order_by(ComplianceEvaluation.created_at.desc())
            )
        ).all()
    )
    return Envelope(
        data=[ComplianceEvaluationResponse.model_validate(x) for x in rows],
        meta=Meta(request_id=request.state.request_id),
    )
