from datetime import datetime
from typing import Literal

from pydantic import Field

from mnemos.schemas.common import APIModel


class IngestionDocumentMetadata(APIModel):
    filename: str
    uploaded_at: datetime
    asset_ids: list[str] = []
    access_classification: str = "internal"


class IngestionRequest(APIModel):
    run_id: str
    document_id: str
    organisation_id: str
    site_id: str
    document_version: int
    document_type: str
    storage_uri: str
    mime_type: str
    sha256: str
    metadata: IngestionDocumentMetadata


class IngestionResult(APIModel):
    run_id: str
    document_id: str
    document_version: int
    status: Literal["succeeded", "partially_succeeded", "failed"]
    chunks_created: int = Field(default=0, ge=0)
    entities_created: int = Field(default=0, ge=0)
    relationships_created: int = Field(default=0, ge=0)
    warnings: list[str] = []
    pipeline_version: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class IngestionRunResponse(APIModel):
    id: str
    document_id: str
    organisation_id: str
    site_id: str
    document_version: int
    status: str
    gateway: str
    chunks_created: int
    entities_created: int
    relationships_created: int
    warnings: list[str]
    pipeline_version: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionEventResponse(APIModel):
    id: str
    ingestion_run_id: str
    stage: str
    progress_percent: int
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}
