from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from mnemos.schemas.common import ORMModel


class QueryContext(BaseModel):
    asset_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)


class QueryCreate(BaseModel):
    site_id: str
    question: str = Field(min_length=3, max_length=5000)
    context: QueryContext = Field(default_factory=QueryContext)
    mode: Literal[
        "general", "investigation", "procedure_lookup", "compliance", "lessons_learned"
    ] = "general"


class QueryAccepted(BaseModel):
    id: str
    status: str
    created_at: datetime


class QueryEventResponse(ORMModel):
    id: str
    query_id: str
    stage: str
    progress_percent: int
    message: str
    created_at: datetime


class ClaimResponse(ORMModel):
    id: str
    external_id: str
    text: str
    support_status: str


class CitationResponse(ORMModel):
    id: str
    claim_id: str | None
    claim_text: str
    support_status: str
    document_id: str | None
    document_title: str
    document_version: int | None
    chunk_id: str | None
    evidence_region_id: str | None
    page_or_sheet: str | None
    locator: str | None
    text_excerpt: str | None
    retrieval_sources: list[str]
    access_allowed: bool


class AgentRunResponse(ORMModel):
    id: str
    query_id: str
    status: str
    gateway: str
    pipeline_version: str | None
    latency_ms: int | None
    retry_count: int
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None


class QueryResponse(ORMModel):
    id: str
    organisation_id: str
    site_id: str
    user_id: str
    question: str
    mode: str
    context_asset_ids: list[str]
    context_document_ids: list[str]
    status: str
    answer: str | None
    confidence_label: str | None
    confidence_score: float | None
    missing_evidence: list[str]
    conflicts: list[dict]
    related_entities: list[dict]
    created_at: datetime
    completed_at: datetime | None
    claims: list[ClaimResponse]
    citations: list[CitationResponse]
    agent_runs: list[AgentRunResponse]
