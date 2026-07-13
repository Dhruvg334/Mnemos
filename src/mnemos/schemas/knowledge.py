from datetime import datetime

from pydantic import Field

from mnemos.schemas.common import ORMModel, APIModel


class KnowledgeCardCreate(APIModel):
    site_id: str
    asset_id: str | None = None
    title: str = Field(min_length=3, max_length=255)
    content: str = Field(min_length=10, max_length=20000)
    supersedes_id: str | None = None


class KnowledgeCardUpdate(APIModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    content: str | None = Field(default=None, min_length=10, max_length=20000)


class KnowledgeReviewRequest(APIModel):
    note: str | None = Field(default=None, max_length=5000)


class KnowledgeCardResponse(ORMModel):
    id: str
    organisation_id: str
    site_id: str
    asset_id: str | None
    title: str
    content: str
    status: str
    version: int
    author_id: str
    reviewer_id: str | None
    review_note: str | None
    supersedes_id: str | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
