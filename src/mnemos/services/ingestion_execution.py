from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.integrations.ingestion import get_ingestion_gateway
from mnemos.models import Document, IngestionEvent, IngestionRun
from mnemos.schemas.ingestion import IngestionDocumentMetadata, IngestionRequest
from mnemos.services.ingestion_pipeline import run_production_ingestion_pipeline


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
        # 1. Run the external extraction (Mock or Real Gateway)
        # Note: In a pure production graphRAG setup, we replace the gateway with our pipeline.
        # But per requirements "do not duplicate ingestion logic", we use the pipeline
        # which incorporates the pgvector/neo4j mapping organically.
        result_stats = await run_production_ingestion_pipeline(db, document)
        
        run.status = "succeeded"
        run.chunks_created = result_stats["chunks_created"]
        run.entities_created = result_stats["entities_created"]
        run.relationships_created = result_stats["relationships_created"]
        run.warnings = []
        run.pipeline_version = "graphrag-v1"
        run.completed_at = datetime.now(UTC)

        await add_ingestion_event(
            db,
            ingestion_run_id=run.id,
            stage="completed",
            progress_percent=100,
            message="Document ingestion completed"
        )
        document.status = "ready"
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
