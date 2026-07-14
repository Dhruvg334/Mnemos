from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models.entities import Document, EvidenceRegion


class LexicalRetriever:
    """
    Handles keyword-based (BM25 or FTS) retrieval.
    Essential for finding specific tags or technical terms
    that might be missed by semantic embedding models.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(self, keywords: str, site_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """
        Executes a Full-Text Search (FTS) against document evidence regions.
        """
        # PostgreSQL FTS example
        # In SQLite (default for dev), we'd use a simplified LIKE or FTS5

        # Simplified implementation for the architecture
        stmt = (
            select(EvidenceRegion)
            .join(Document)
            .where(EvidenceRegion.text_excerpt.ilike(f"%{keywords}%"))
        )

        if site_id:
            stmt = stmt.where(Document.site_id == site_id)

        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        regions = result.scalars().all()

        results = []
        for reg in regions:
            results.append({
                "id": reg.id,
                "text": reg.text_excerpt,
                "metadata": reg.metadata_json,
                "document_id": reg.document_id,
                "page": reg.page_or_sheet
            })
        return results
