from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.integrations.storage import S3Storage
from mnemos.models import Document, EvidenceRegion, ProcessingJob
from mnemos.models.vector import DocumentChunk
from mnemos.services.document_extraction import ImageOnlyPdfError, chunk_sections, extract_document


class IngestionLifecycle:
    def __init__(self) -> None:
        self.storage = S3Storage()

    async def queue(self, db: AsyncSession, document: Document) -> ProcessingJob:
        job = ProcessingJob(
            document_id=document.id, status="queued", stage="validating", progress_percent=0
        )
        document.status = "queued"
        db.add(job)
        await db.flush()
        return job

    async def run(self, db: AsyncSession, document: Document, job: ProcessingJob) -> None:
        job.status = "running"
        job.stage = "parsing"
        job.progress_percent = 15
        job.started_at = datetime.now(UTC)
        document.status = "processing"
        try:
            raw = await self.storage.read_object(document.storage_key or "")
            sections = extract_document(raw, document.mime_type, document.filename)
            job.stage = "persisting_evidence"
            job.progress_percent = 55
            for section in sections:
                db.add(
                    EvidenceRegion(
                        document_id=document.id,
                        page_or_sheet=section.page_or_sheet,
                        locator=section.locator,
                        text_excerpt=section.text[:4000],
                        metadata_json={
                            "section": section.section,
                            "source": "document_extraction",
                            "mime_type": document.mime_type,
                        },
                    )
                )
            for index, (section, content) in enumerate(chunk_sections(sections)):
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        revision_id=str(document.version),
                        page_number=int(section.page_or_sheet)
                        if (section.page_or_sheet or "").isdigit()
                        else None,
                        chunk_index=index,
                        content=content,
                        metadata_json={
                            "filename": document.filename,
                            "locator": section.locator,
                            "section": section.section,
                            "embedding_status": "pending",
                        },
                        site_id=document.site_id,
                        tenant_id=document.organisation_id,
                    )
                )
            await db.flush()
            job.stage = "completed"
            job.progress_percent = 100
            job.status = "succeeded"
            job.completed_at = datetime.now(UTC)
            document.status = "ready"
        except ImageOnlyPdfError as exc:
            job.status = "failed"
            job.stage = "failed"
            job.progress_percent = 100
            job.error_code = exc.code
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            document.status = "failed"
        except Exception as exc:
            job.status = "failed"
            job.stage = "failed"
            job.progress_percent = 100
            job.error_code = getattr(exc, "code", "EXTRACTION_FAILED")
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            document.status = "failed"
