from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models import Document, EvidenceRegion, ProcessingJob


class IngestionLifecycle:
    async def queue(self, db: AsyncSession, document: Document) -> ProcessingJob:
        job = ProcessingJob(
            document_id=document.id, status="queued", stage="validating", progress_percent=0
        )
        document.status = "queued"
        db.add(job)
        await db.flush()
        return job

    async def run_mock(self, db: AsyncSession, document: Document, job: ProcessingJob) -> None:
        job.status = "running"
        job.stage = "parsing"
        job.progress_percent = 20
        job.started_at = datetime.now(UTC)
        job.stage = "extracting_entities"
        job.progress_percent = 60
        db.add(
            EvidenceRegion(
                document_id=document.id,
                page_or_sheet="1",
                locator="document",
                metadata_json={"source": "mock_ingestion", "document_type": document.document_type},
            )
        )
        job.stage = "indexing"
        job.progress_percent = 90
        job.status = "succeeded"
        job.stage = "completed"
        job.progress_percent = 100
        job.completed_at = datetime.now(UTC)
        document.status = "ready"
