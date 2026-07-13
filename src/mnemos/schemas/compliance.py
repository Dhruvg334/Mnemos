from datetime import datetime
from typing import Literal

from pydantic import Field

from mnemos.schemas.common import ORMModel, APIModel


class RequirementCreate(APIModel):
    organisation_id: str
    code: str = Field(min_length=2, max_length=128)
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3, max_length=10000)
    source: str = Field(min_length=2, max_length=255)


class RequirementResponse(ORMModel):
    id: str
    organisation_id: str
    code: str
    title: str
    description: str
    source: str
    status: str
    created_at: datetime


class ComplianceEvaluationCreate(APIModel):
    site_id: str
    asset_id: str
    requirement_ids: list[str] = Field(min_length=1)


class ComplianceFinding(APIModel):
    requirement_id: str
    result: Literal["compliant", "non_compliant", "insufficient_evidence", "not_applicable"]
    summary: str
    evidence_region_ids: list[str] = Field(default_factory=list)


class ComplianceReviewRequest(APIModel):
    note: str | None = Field(default=None, max_length=5000)


class ComplianceEvaluationResponse(ORMModel):
    id: str
    organisation_id: str
    site_id: str
    asset_id: str
    requirement_ids: list[str]
    status: str
    overall_result: str | None
    findings: list[dict]
    missing_evidence: list[str]
    conflicts: list[dict]
    created_by: str
    reviewed_by: str | None
    review_note: str | None
    created_at: datetime
    completed_at: datetime | None
    reviewed_at: datetime | None
