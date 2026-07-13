from datetime import datetime

from pydantic import Field

from mnemos.schemas.common import ORMModel, APIModel


class DocumentCreate(APIModel):
    site_id: str
    filename: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\]+$")
    mime_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    document_type: str = Field(min_length=1, max_length=128)


class DocumentResponse(ORMModel):
    id: str
    organisation_id: str
    site_id: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    document_type: str
    status: str
    storage_key: str | None
    version: int
    uploaded_at: datetime
