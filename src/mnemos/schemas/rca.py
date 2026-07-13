from datetime import datetime
from typing import Literal

from pydantic import Field

from mnemos.schemas.common import APIModel, ORMModel


class RCACreate(APIModel):
    site_id: str
    asset_id: str
    title: str = Field(min_length=3, max_length=255)
    problem_statement: str = Field(min_length=10, max_length=10000)
    severity: Literal["low", "medium", "high", "critical"] = "medium"


class RCAUpdate(APIModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    problem_statement: str | None = Field(default=None, min_length=10, max_length=10000)
    severity: Literal["low", "medium", "high", "critical"] | None = None


class RCAObservationCreate(APIModel):
    observation_type: Literal["fact", "event", "measurement", "missing_evidence"]
    text: str = Field(min_length=3, max_length=10000)
    evidence_region_id: str | None = None
    occurred_at: datetime | None = None


class RCAHypothesisCreate(APIModel):
    text: str = Field(min_length=3, max_length=10000)
    support_status: Literal[
        "supported", "partially_supported", "conflicting", "unsupported", "not_evaluated"
    ] = "not_evaluated"
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_region_ids: list[str] = Field(default_factory=list)


class RCAActionCreate(APIModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3, max_length=10000)
    owner_id: str | None = None
    due_at: datetime | None = None


class RCAReviewRequest(APIModel):
    note: str | None = Field(default=None, max_length=5000)


class RCAObservationResponse(ORMModel):
    id: str
    observation_type: str
    text: str
    evidence_region_id: str | None
    occurred_at: datetime | None
    created_at: datetime


class RCAHypothesisResponse(ORMModel):
    id: str
    text: str
    support_status: str
    confidence_score: float | None
    evidence_region_ids: list[str]
    created_at: datetime


class RCAActionResponse(ORMModel):
    id: str
    title: str
    description: str
    status: str
    owner_id: str | None
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RCAResponse(ORMModel):
    id: str
    organisation_id: str
    site_id: str
    asset_id: str
    title: str
    problem_statement: str
    status: str
    severity: str
    created_by: str
    submitted_by: str | None
    approved_by: str | None
    rejected_by: str | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    closed_at: datetime | None
    observations: list[RCAObservationResponse] = Field(default_factory=list)
    hypotheses: list[RCAHypothesisResponse] = Field(default_factory=list)
    actions: list[RCAActionResponse] = Field(default_factory=list)
