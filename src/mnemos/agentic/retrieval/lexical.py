"""Lexical (keyword) retriever with date, revision, and permission filters."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models.entities import Document, DocumentVersion, EvidenceRegion


class LexicalRetriever:
    """Keyword-based retrieval using ILIKE against evidence regions.

    Supports:
    - Site/organisation permission filtering
    - Date range filtering (via Document.created_at)
    - Revision filtering (current-only or explicit versions)
    - Document ID scoping
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        keywords: str,
        *,
        site_id: str | None = None,
        limit: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
        latest_version_only: bool = True,
        document_versions: list[int] | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute keyword search with optional filters."""
        stmt = (
            select(EvidenceRegion, Document)
            .join(Document, EvidenceRegion.document_id == Document.id)
            .where(EvidenceRegion.text_excerpt.ilike(f"%{keywords}%"))
        )

        # Permission boundary
        if site_id:
            stmt = stmt.where(Document.site_id == site_id)

        # Date filters
        if date_from:
            stmt = stmt.where(Document.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Document.created_at <= date_to)

        # Document ID scoping
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))

        # Revision filters
        if latest_version_only:
            # Only match evidence regions from the current document version
            stmt = stmt.where(Document.version == DocumentVersion.version).join(
                DocumentVersion,
                (DocumentVersion.document_id == Document.id)
                & (DocumentVersion.version == Document.version),
            )
        elif document_versions:
            stmt = stmt.where(Document.version.in_(document_versions))

        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        rows = result.all()

        results: list[dict[str, Any]] = []
        for region, doc in rows:
            results.append(
                {
                    "id": region.id,
                    "text": region.text_excerpt,
                    "metadata": region.metadata_json or {},
                    "document_id": region.document_id,
                    "page": region.page_or_sheet,
                    "document_version": doc.version,
                    "score": 1.0,
                }
            )
        return results
