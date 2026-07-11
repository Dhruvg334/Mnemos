from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from mnemos.schemas.common import ORMModel


class QueryContext(BaseModel):
    asset_ids: list[str] = []
    document_ids: list[str] = []


class QueryCreate(BaseModel):
    site_id: str
    question: str = Field(min_length=3, max_length=5000)
    context: QueryContext = QueryContext()
    mode: Literal[
        "general", "investigation", "procedure_lookup", "compliance", "lessons_learned"
    ] = "general"


class CitationResponse(ORMModel):
    id: str
    claim_text: str
    support_status: str
    document_title: str
    page_or_sheet: str | None
    locator: str | None
    text_excerpt: str | None
    access_allowed: bool


class QueryResponse(ORMModel):
    id: str
    organisation_id: str
    site_id: str
    user_id: str
    question: str
    mode: str
    status: str
    answer: str | None
    confidence_label: str | None
    confidence_score: float | None
    missing_evidence: list[str]
    conflicts: list[dict]
    related_entities: list[dict]
    created_at: datetime
    completed_at: datetime | None
    citations: list[CitationResponse]
