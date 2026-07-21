from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.integrations.ingestion import get_ingestion_gateway
from mnemos.models import Document, IngestionEvent, IngestionRun
from mnemos.schemas.ingestion import IngestionDocumentMetadata, IngestionRequest


def _hash_payload(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def add_ingestion_event(
    db: AsyncSession,
    *,
    ingestion_run_id: str,
    stage: str,
    progress_percent: int,
    message: str,
) -> None:
    db.add(
        IngestionEvent(
            ingestion_run_id=ingestion_run_id,
            stage=stage,
            progress_percent=progress_percent,
            message=message,
        )
    )
    await db.flush()


async def execute_ingestion(
    db: AsyncSession,
    *,
    document: Document,
) -> IngestionRun:
    if not document.storage_key:
        raise ValueError("Document has no storage key")

    gateway = get_ingestion_gateway()
    run = IngestionRun(
        document_id=document.id,
        organisation_id=document.organisation_id,
        site_id=document.site_id,
        document_version=document.version,
        status="running",
        gateway=gateway.name,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.flush()

    await add_ingestion_event(
        db,
        ingestion_run_id=run.id,
        stage="validating",
        progress_percent=5,
        message="Validating document handoff",
    )

    request = IngestionRequest(
        run_id=run.id,
        document_id=document.id,
        organisation_id=document.organisation_id,
        site_id=document.site_id,
        document_version=document.version,
        document_type=document.document_type,
        storage_uri=f"s3://{document.storage_key}",
        mime_type=document.mime_type,
        sha256=document.sha256,
        metadata=IngestionDocumentMetadata(
            filename=document.filename,
            uploaded_at=document.uploaded_at,
        ),
    )
    run.request_payload_hash = _hash_payload(request.model_dump(mode="json"))

    await add_ingestion_event(
        db,
        ingestion_run_id=run.id,
        stage="parsing",
        progress_percent=20,
        message="Sending document to ingestion service",
    )

    try:
        # Original external gateway extraction
        result = await gateway.ingest_document(request)

        run.response_payload_hash = _hash_payload(result.model_dump(mode="json"))
        run.status = result.status
        run.chunks_created = result.chunks_created
        run.entities_created = result.entities_created
        run.relationships_created = result.relationships_created
        run.warnings = result.warnings
        run.pipeline_version = result.pipeline_version
        run.error_code = result.error_code
        run.error_message = result.error_message
        run.completed_at = datetime.now(UTC)

        await add_ingestion_event(
            db,
            ingestion_run_id=run.id,
            stage="completed" if result.status != "failed" else "failed",
            progress_percent=100,
            message="Document ingestion completed"
            if result.status != "failed"
            else "Document ingestion failed",
        )
        document.status = (
            "ready"
            if result.status == "succeeded"
            else "partially_ready"
            if result.status == "partially_succeeded"
            else "failed"
        )
        return run
    except Exception as exc:
        run.status = "failed"
        run.error_code = getattr(exc, "code", "INGESTION_FAILED")
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
        document.status = "failed"
        await add_ingestion_event(
            db,
            ingestion_run_id=run.id,
            stage="failed",
            progress_percent=100,
            message="Document ingestion failed",
        )
        raise
