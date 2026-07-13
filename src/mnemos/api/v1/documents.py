from __future__ import annotations
import re, uuid
from datetime import UTC, datetime, timedelta
from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from mnemos.api.deps import Principal, get_principal, require_site_access
from mnemos.core.config import settings
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.integrations.storage import S3Storage
from mnemos.models import Document, DocumentVersion, EvidenceRegion, ProcessingJob, Site, UploadSession
from mnemos.schemas.common import Envelope, Meta
from mnemos.schemas.document import DocumentResponse
from mnemos.schemas.upload import EvidenceRegionResponse, ProcessingStatusResponse, UploadConfirmRequest, UploadSessionCreate, UploadSessionResponse
from mnemos.services.audit import write_audit
from mnemos.services.ingestion import IngestionLifecycle
from mnemos.services.ingestion_execution import execute_ingestion

router = APIRouter(prefix="/documents", tags=["documents"])
storage = S3Storage(); ingestion = IngestionLifecycle()

def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    if not value: raise AppError("VALIDATION_ERROR", "Filename is not valid.", 422)
    return value[:180]

async def load_document(db: AsyncSession, document_id: str, principal: Principal) -> Document:
    doc = await db.get(Document, document_id)
    if doc is None: raise AppError("NOT_FOUND", "Document not found.", 404)
    require_site_access(principal, doc.site_id); return doc

@router.post("/upload-session", response_model=Envelope[UploadSessionResponse], status_code=201)
async def create_upload_session(payload: UploadSessionCreate, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    membership = require_site_access(principal, payload.site_id)
    site = await db.get(Site, payload.site_id)
    if site is None: raise AppError("NOT_FOUND", "Site not found.", 404)
    if payload.mime_type not in settings.allowed_upload_mime_types:
        raise AppError("UNSUPPORTED_FILE_TYPE", "The supplied file type is not supported.", 415)
    if payload.size_bytes > settings.max_upload_size_bytes:
        raise AppError("FILE_TOO_LARGE", "The supplied file exceeds the configured upload limit.", 413, details={"max_size_bytes":settings.max_upload_size_bytes})
    duplicate = await db.scalar(select(Document).where(Document.site_id==site.id, Document.sha256==payload.sha256.lower(), Document.status!="archived"))
    if duplicate: raise AppError("CONFLICT", "A document with the same checksum already exists at this site.", 409, details={"document_id":duplicate.id})
    doc = Document(organisation_id=site.organisation_id, site_id=site.id, filename=payload.filename, mime_type=payload.mime_type, size_bytes=payload.size_bytes, sha256=payload.sha256.lower(), document_type=payload.document_type, status="uploaded")
    db.add(doc); await db.flush()
    key=f"{site.organisation_id}/{site.id}/{doc.id}/v1/{uuid.uuid4().hex}-{safe_filename(payload.filename)}"
    expires=datetime.now(UTC)+timedelta(minutes=settings.upload_session_expire_minutes)
    session=UploadSession(document_id=doc.id, object_key=key, expires_at=expires); db.add(session); await db.flush()
    await storage.ensure_bucket()
    url=await storage.create_presigned_upload(key,payload.mime_type,settings.upload_session_expire_minutes*60)
    await write_audit(db, organisation_id=site.organisation_id, site_id=site.id, actor_id=principal.user.id, action="document.upload_session_created", resource_type="document", resource_id=doc.id, request_id=request.state.request_id, metadata={"role":membership.role,"upload_session_id":session.id})
    await db.commit()
    return Envelope(data=UploadSessionResponse(upload_session_id=session.id, document_id=doc.id, upload_url=url, expires_at=expires, required_headers={"Content-Type":payload.mime_type}), meta=Meta(request_id=request.state.request_id))

@router.post("/{document_id}/confirm", response_model=Envelope[DocumentResponse])
async def confirm_upload(document_id: str, payload: UploadConfirmRequest, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    doc=await load_document(db,document_id,principal)
    session=await db.scalar(select(UploadSession).where(UploadSession.id==payload.upload_session_id, UploadSession.document_id==doc.id))
    if session is None: raise AppError("NOT_FOUND", "Upload session not found.", 404)
    if session.status!="pending": raise AppError("CONFLICT", "Upload session is not pending.", 409)
    if session.expires_at < datetime.now(UTC): session.status="expired"; await db.commit(); raise AppError("CONFLICT", "Upload session has expired.", 409)
    if not await storage.object_exists(session.object_key): raise AppError("DOCUMENT_NOT_READY", "The object has not been uploaded.", 409, retryable=True)
    actual=await storage.object_size(session.object_key)
    if actual!=doc.size_bytes:
        await storage.delete_object(session.object_key); doc.status="failed"; session.status="cancelled"; await db.commit()
        raise AppError("VALIDATION_ERROR", "Uploaded object size does not match the declared size.", 422, details={"declared_size_bytes":doc.size_bytes,"actual_size_bytes":actual})
    doc.storage_key=session.object_key; session.status="uploaded"; session.completed_at=datetime.now(UTC)
    db.add(DocumentVersion(document_id=doc.id,version=doc.version,storage_key=session.object_key,sha256=doc.sha256,size_bytes=doc.size_bytes))
    job=await ingestion.queue(db,doc); await ingestion.run_mock(db,doc,job)
    await write_audit(db, organisation_id=doc.organisation_id, site_id=doc.site_id, actor_id=principal.user.id, action="document.upload_confirmed", resource_type="document", resource_id=doc.id, request_id=request.state.request_id, metadata={"upload_session_id":session.id,"processing_job_id":job.id})
    await db.commit(); await db.refresh(doc)
    return Envelope(data=DocumentResponse.model_validate(doc), meta=Meta(request_id=request.state.request_id))

@router.get("", response_model=Envelope[list[DocumentResponse]])
async def list_documents(request: Request, site_id: str, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    require_site_access(principal,site_id)
    docs=list((await db.scalars(select(Document).where(Document.site_id==site_id).order_by(desc(Document.uploaded_at)))).all())
    return Envelope(data=[DocumentResponse.model_validate(x) for x in docs],meta=Meta(request_id=request.state.request_id))

@router.get("/{document_id}", response_model=Envelope[DocumentResponse])
async def get_document(document_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    doc=await load_document(db,document_id,principal)
    return Envelope(data=DocumentResponse.model_validate(doc),meta=Meta(request_id=request.state.request_id))

@router.get("/{document_id}/status", response_model=Envelope[ProcessingStatusResponse])
async def get_status(document_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    doc=await load_document(db,document_id,principal)
    job=await db.scalar(select(ProcessingJob).where(ProcessingJob.document_id==doc.id).order_by(desc(ProcessingJob.created_at)))
    data=ProcessingStatusResponse(document_id=doc.id,document_status=doc.status,job_id=job.id if job else None,job_status=job.status if job else None,stage=job.stage if job else None,progress_percent=job.progress_percent if job else 0,warnings=list(job.warnings or []) if job else [],updated_at=(job.completed_at or job.started_at or job.created_at) if job else None)
    return Envelope(data=data,meta=Meta(request_id=request.state.request_id))

@router.post("/{document_id}/reprocess", response_model=Envelope[ProcessingStatusResponse], status_code=202)
async def reprocess(document_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    doc=await load_document(db,document_id,principal)
    if not doc.storage_key: raise AppError("DOCUMENT_NOT_READY", "Document has no stored object.", 409)
    job=await ingestion.queue(db,doc); await ingestion.run_mock(db,doc,job); await db.commit()
    data=ProcessingStatusResponse(document_id=doc.id,document_status=doc.status,job_id=job.id,job_status=job.status,stage=job.stage,progress_percent=job.progress_percent,warnings=list(job.warnings or []),updated_at=job.completed_at or job.started_at or job.created_at)
    return Envelope(data=data,meta=Meta(request_id=request.state.request_id))

@router.get("/{document_id}/evidence/{evidence_region_id}", response_model=Envelope[EvidenceRegionResponse])
async def get_evidence(document_id: str, evidence_region_id: str, request: Request, principal: Principal = Depends(get_principal), db: AsyncSession = Depends(get_db)):
    doc=await load_document(db,document_id,principal)
    ev=await db.scalar(select(EvidenceRegion).where(EvidenceRegion.id==evidence_region_id,EvidenceRegion.document_id==doc.id))
    if ev is None: raise AppError("NOT_FOUND", "Evidence region not found.", 404)
    data=EvidenceRegionResponse(id=ev.id,document_id=ev.document_id,page_or_sheet=ev.page_or_sheet,locator=ev.locator,text_excerpt=ev.text_excerpt,metadata=dict(ev.metadata_json or {}))
    return Envelope(data=data,meta=Meta(request_id=request.state.request_id))
