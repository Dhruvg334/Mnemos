"""Bounded specialist-agent enrichment through governed MCP tools."""

from __future__ import annotations

from typing import Any

from mnemos.agentic.schemas.base import EvidenceSource


def scoped_asset_ids(
    state: dict[str, Any],
    evidence: list[EvidenceSource],
    *,
    limit: int = 2,
) -> list[str]:
    """Return deduplicated asset IDs already present in authorized workflow state."""
    context = state.get("context", {})
    candidates: list[str] = []
    for value in context.get("asset_ids", []):
        if isinstance(value, str) and value:
            candidates.append(value)
    for entity in context.get("resolved_entities", []):
        entity_id = (
            entity.get("entity_id")
            if isinstance(entity, dict)
            else getattr(entity, "entity_id", None)
        )
        if isinstance(entity_id, str) and entity_id:
            candidates.append(entity_id)
    for source in evidence:
        asset_id = source.metadata.get("asset_id")
        if isinstance(asset_id, str) and asset_id:
            candidates.append(asset_id)

    return list(dict.fromkeys(candidates))[:limit]


def scoped_document_ids(evidence: list[EvidenceSource], *, limit: int = 4) -> list[str]:
    """Return deduplicated document IDs already represented by verified evidence."""
    values = [source.provenance.document_id for source in evidence if source.provenance.document_id]
    return list(dict.fromkeys(values))[:limit]
