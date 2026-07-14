import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.schemas.base import ResolvedEntity
from mnemos.models.entities import Asset, AssetAlias


class AssetIdentityResolver:
    """
    High-fidelity industrial asset identity resolution.
    Handles:
    - Normalization: P-101 == P101 == p 101
    - OCR errors: O/0, I/1/L, S/5, B/8, G/6, Z/2
    - Punctuation variants: '.' '-' '/' '_'
    - Aliases & Historical Names: Resolved via AssetAlias table
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def _normalize(self, text: str) -> str:
        """Deep normalization for robust matching."""
        if not text:
            return ""
        # Convert to NFKD to separate characters and accents
        text = unicodedata.normalize('NFKD', text)
        # Keep only alphanumeric
        text = re.sub(r'[^A-Z0-9]', '', text.upper())
        return text

    def _generate_fuzzy_variants(self, normalized: str) -> set[str]:
        """Generates common OCR substitution variants for better recall."""
        substitutions = {
            'O': '0', '0': 'O',
            'I': '1', '1': 'I', 'L': '1',
            'S': '5', '5': 'S',
            'B': '8', '8': 'B',
            'G': '6', '6': 'G',
            'Z': '2', '2': 'Z'
        }
        variants = {normalized}

        # We generate variants by replacing one character at a time
        # for common OCR ambiguity pairs.
        for i, char in enumerate(normalized):
            if char in substitutions:
                variant = normalized[:i] + substitutions[char] + normalized[i+1:]
                variants.add(variant)

        return variants

    async def resolve(self, mention: str, site_id: str | None = None) -> list[ResolvedEntity]:
        """
        Resolves a string mention to a list of candidate assets.
        """
        raw_normalized = self._normalize(mention)
        if not raw_normalized:
            return []

        variants = self._generate_fuzzy_variants(raw_normalized)

        # 1. Database Query: Match against normalized tags and aliases
        # Using functional index-friendly comparisons if possible,
        # otherwise on-the-fly normalization.
        stmt = (
            select(Asset)
            .outerjoin(AssetAlias)
            .where(
                or_(
                    # Match normalized asset_tag
                    func.replace(func.replace(func.replace(func.upper(Asset.asset_tag), '-', ''), ' ', ''), '.', '').in_(list(variants)),
                    # Match pre-normalized aliases
                    AssetAlias.normalized_alias.in_(list(variants)),
                    # Match raw tags just in case
                    Asset.asset_tag == mention
                )
            )
        )

        if site_id:
            stmt = stmt.where(Asset.site_id == site_id)

        result = await self.db.execute(stmt)
        assets = result.scalars().unique().all()

        resolved_entities = []
        for asset in assets:
            asset_norm = self._normalize(asset.asset_tag)

            # Confidence Scoring
            if asset.asset_tag == mention:
                confidence = 1.0
            elif asset_norm == raw_normalized:
                confidence = 0.95
            elif any(v == asset_norm for v in variants):
                confidence = 0.85 # OCR variant match
            else:
                confidence = 0.7 # Alias or indirect match

            resolved_entities.append(ResolvedEntity(
                original_text=mention,
                entity_id=asset.id,
                entity_type="ASSET",
                confidence=confidence,
                canonical_name=asset.name,
                metadata={
                    "tag": asset.asset_tag,
                    "type": asset.asset_type,
                    "site_id": asset.site_id
                }
            ))

        # Sort by confidence
        resolved_entities.sort(key=lambda x: x.confidence, reverse=True)
        return resolved_entities
