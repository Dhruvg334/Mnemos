from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.models import Document, Site
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.document import DocumentCreate, DocumentResponse
from mnemos.services.audit import write_audit

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=Envelope[DocumentResponse], status_code=201)
async def create_document(
    payload: DocumentCreate,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[DocumentResponse]:
    membership = require_site_access(principal, payload.site_id)
    site = await db.get(Site, payload.site_id)
    if site is None:
        raise AppError("NOT_FOUND", "Site not found.", 404)

    duplicate = await db.scalar(
        select(Document).where(
            Document.site_id == payload.site_id,
            Document.sha256 == payload.sha256,
        )
    )
    if duplicate is not None:
        raise AppError(
            "CONFLICT",
            "A document with the same checksum already exists at this site.",
            409,
            details={"document_id": duplicate.id},
        )

    document = Document(
        organisation_id=site.organisation_id,
        site_id=payload.site_id,
        filename=payload.filename,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        document_type=payload.document_type,
        status="uploaded",
    )
    db.add(document)
    await db.flush()
    await write_audit(
        db,
        organisation_id=site.organisation_id,
        site_id=site.id,
        actor_id=principal.user.id,
        action="document.created",
        resource_type="document",
        resource_id=document.id,
        request_id=request.state.request_id,
        metadata={"role": membership.role},
    )
    await db.commit()
    await db.refresh(document)
    return Envelope(
        data=DocumentResponse.model_validate(document),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("", response_model=Envelope[list[DocumentResponse]])
async def list_documents(
    request: Request,
    site_id: str,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
) -> Envelope[list[DocumentResponse]]:
    require_site_access(principal, site_id)
    documents = list(
        (await db.scalars(select(Document).where(Document.site_id == site_id))).all()
    )
    return Envelope(
        data=[DocumentResponse.model_validate(document) for document in documents],
        meta=Meta(request_id=request.state.request_id),
    )
