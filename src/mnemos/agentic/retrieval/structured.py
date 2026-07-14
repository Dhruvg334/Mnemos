from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models.entities import Asset, KnowledgeCard, RCACase, Site


class StructuredRetriever:
    """
    Retrieves structured operational data and Expert Memory from the relational database.
    Focuses on:
    - Asset specifications
    - Maintenance history
    - Knowledge Cards (Expert Memory)
    - Site-specific configuration
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_asset_specs(self, asset_id: str) -> dict[str, Any]:
        """Fetches technical specifications for a resolved asset."""
        stmt = select(Asset).where(Asset.id == asset_id)
        result = await self.db.execute(stmt)
        asset = result.scalar_one_or_none()
        if not asset:
            return {}

        return {
            "asset_tag": asset.asset_tag,
            "name": asset.name,
            "type": asset.asset_type,
            "status": asset.status
        }

    async def get_maintenance_history(self, asset_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Retrieves historical RCA cases and observations for an asset."""
        stmt = (
            select(RCACase)
            .where(RCACase.asset_id == asset_id)
            .order_by(RCACase.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        cases = result.scalars().all()

        history = []
        for case in cases:
            history.append({
                "case_id": case.id,
                "title": case.title,
                "problem_statement": case.problem_statement,
                "status": case.status,
                "severity": case.severity,
                "created_at": case.created_at.isoformat()
            })
        return history

    async def get_knowledge_cards(self, asset_id: str) -> list[dict[str, Any]]:
        """
        Retrieves Expert Memory (Knowledge Cards) linked to an asset.
        """
        stmt = (
            select(KnowledgeCard)
            .where(KnowledgeCard.asset_id == asset_id, KnowledgeCard.status == "approved")
            .order_by(KnowledgeCard.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        cards = result.scalars().all()

        return [{
            "card_id": card.id,
            "title": card.title,
            "content": card.content,
            "version": card.version,
            "updated_at": card.updated_at.isoformat()
        } for card in cards]

    async def get_site_context(self, site_id: str) -> dict[str, Any]:
        """Retrieves operational context for a specific site."""
        stmt = select(Site).where(Site.id == site_id)
        result = await self.db.execute(stmt)
        site = result.scalar_one_or_none()
        if not site:
            return {}
        return {
            "name": site.name,
            "code": site.code,
            "timezone": site.timezone
        }
