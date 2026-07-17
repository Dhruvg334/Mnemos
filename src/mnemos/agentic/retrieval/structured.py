"""Structured (SQL) retriever with date and permission filters."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models.entities import Asset, KnowledgeCard, RCACase, Site


class StructuredRetriever:
    """Relational database retriever for structured operational data.

    Supports:
    - Asset specifications lookup
    - Maintenance history with date-range filtering
    - Knowledge Cards (Expert Memory) with date-range filtering
    - Site context retrieval
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_asset_specs(self, asset_id: str) -> dict[str, Any]:
        """Fetch technical specifications for a resolved asset."""
        stmt = select(Asset).where(Asset.id == asset_id)
        result = await self.db.execute(stmt)
        asset = result.scalar_one_or_none()
        if not asset:
            return {}
        return {
            "asset_tag": asset.asset_tag,
            "name": asset.name,
            "type": asset.asset_type,
            "status": asset.status,
        }

    async def get_maintenance_history(
        self,
        asset_id: str,
        *,
        limit: int = 5,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve historical RCA cases for an asset with optional date range."""
        stmt = (
            select(RCACase)
            .where(RCACase.asset_id == asset_id)
        )
        if date_from:
            stmt = stmt.where(RCACase.created_at >= date_from)
        if date_to:
            stmt = stmt.where(RCACase.created_at <= date_to)

        stmt = stmt.order_by(RCACase.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        cases = result.scalars().all()

        return [
            {
                "case_id": case.id,
                "title": case.title,
                "problem_statement": case.problem_statement,
                "status": case.status,
                "severity": case.severity,
                "created_at": case.created_at.isoformat(),
            }
            for case in cases
        ]

    async def get_knowledge_cards(
        self,
        asset_id: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve approved Knowledge Cards for an asset with optional date range."""
        stmt = (
            select(KnowledgeCard)
            .where(KnowledgeCard.asset_id == asset_id, KnowledgeCard.status == "approved")
        )
        if date_from:
            stmt = stmt.where(KnowledgeCard.created_at >= date_from)
        if date_to:
            stmt = stmt.where(KnowledgeCard.created_at <= date_to)

        stmt = stmt.order_by(KnowledgeCard.updated_at.desc())
        result = await self.db.execute(stmt)
        cards = result.scalars().all()

        return [
            {
                "card_id": card.id,
                "title": card.title,
                "content": card.content,
                "version": card.version,
                "updated_at": card.updated_at.isoformat(),
            }
            for card in cards
        ]

    async def get_site_context(self, site_id: str) -> dict[str, Any]:
        """Retrieve operational context for a specific site."""
        stmt = select(Site).where(Site.id == site_id)
        result = await self.db.execute(stmt)
        site = result.scalar_one_or_none()
        if not site:
            return {}
        return {
            "name": site.name,
            "code": site.code,
            "timezone": site.timezone,
        }
