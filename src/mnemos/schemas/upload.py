from mnemos.schemas.common import APIModel
from datetime import datetime
from pydantic import Field

class UploadSessionCreate(APIModel):
    site_id: str
    filename: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\]+$")
    mime_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    document_type: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.-]*$")

class UploadSessionResponse(APIModel):
    upload_session_id: str
    document_id: str
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]

class UploadConfirmRequest(APIModel):
    upload_session_id: str

class ProcessingStatusResponse(APIModel):
    document_id: str
    document_status: str
    job_id: str | None
    job_status: str | None
    stage: str | None
    progress_percent: int
    warnings: list[str]
    updated_at: datetime | None

class EvidenceRegionResponse(APIModel):
    id: str
    document_id: str
    page_or_sheet: str | None
    locator: str | None
    text_excerpt: str | None
    metadata: dict
    access_allowed: bool = True
