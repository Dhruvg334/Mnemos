"""Superseded Document Detector.

Detects and filters out superseded document versions to ensure
only the most current evidence is used.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.utils.logging import StructuredLogger
from mnemos.models.entities import Document, DocumentVersion

logger = StructuredLogger("superseded_detector")


class SupersededDetector:
    """Detects and filters superseded document versions.

    Queries the database to find which document versions are current
    vs superseded, and provides filtering for evidence.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_current_version_ids(self) -> set[str]:
        """Get all document IDs that are at their latest version."""
        stmt = (
            select(Document.id)
            .join(DocumentVersion, DocumentVersion.document_id == Document.id)
            .where(Document.version == DocumentVersion.version)
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def get_superseded_region_ids(self) -> set[str]:
        """Get evidence region IDs belonging to superseded document versions."""
        stmt = (
            select("id")
            .select_from("evidence_regions")
            .where(
                ~select(Document.id)
                .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                .where(Document.version == DocumentVersion.version)
                .correlate("evidence_regions")
                .exists()
            )
        )
        try:
            result = await self.db.execute(stmt)
            return {row[0] for row in result.all()}
        except Exception:
            logger.warning("Could not query superseded regions, returning empty set")
            return set()

    def filter_superseded(
        self,
        candidates: list[dict[str, Any]],
        current_version_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Filter out candidates from superseded document versions."""
        if current_version_ids is None:
            return candidates

        filtered: list[dict[str, Any]] = []
        removed = 0

        for cand in candidates:
            meta = cand.get("metadata", {})
            doc_id = meta.get("document_id")

            if doc_id and doc_id not in current_version_ids:
                removed += 1
                continue

            # Also check if metadata explicitly says superseded
            if meta.get("is_superseded", False):
                removed += 1
                continue

            filtered.append(cand)

        if removed:
            logger.info(f"Filtered {removed} superseded candidates")
        return filtered

    def mark_versions(
        self,
        candidates: list[dict[str, Any]],
        current_version_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Mark candidates with is_latest_version flag."""
        for cand in candidates:
            doc_id = cand.get("metadata", {}).get("document_id")
            if doc_id:
                cand["metadata"]["is_latest_version"] = doc_id in current_version_ids
            else:
                cand["metadata"]["is_latest_version"] = True
        return candidates
