from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models import (
    Asset,
    AssetAlias,
    AssetRelationship,
    ComplianceEvaluation,
    KnowledgeCard,
    Query,
    RCACase,
)
from mnemos.schemas.asset import (
    AssetGraphEdge,
    AssetGraphNode,
    AssetGraphResponse,
    AssetTimelineItem,
    AssetTimelineResponse,
)


async def build_asset_graph(
    db: AsyncSession,
    *,
    asset: Asset,
    max_depth: int = 2,
    max_edges: int = 100,
) -> AssetGraphResponse:
    nodes: dict[str, AssetGraphNode] = {
        asset.id: AssetGraphNode(
            id=asset.id,
            label=f"{asset.asset_tag} — {asset.name}",
            node_type="asset",
            metadata={"asset_type": asset.asset_type, "status": asset.status},
        )
    }
    edges: list[AssetGraphEdge] = []
    frontier = {asset.id}
    visited = {asset.id}

    for _ in range(max_depth):
        if not frontier or len(edges) >= max_edges:
            break

        rows = list(
            (
                await db.scalars(
                    select(AssetRelationship).where(
                        AssetRelationship.site_id == asset.site_id,
                        or_(
                            AssetRelationship.source_asset_id.in_(frontier),
                            AssetRelationship.target_asset_id.in_(frontier),
                        ),
                    )
                )
            ).all()
        )

        next_frontier: set[str] = set()
        for row in rows:
            if len(edges) >= max_edges:
                break
            if any(edge.id == row.id for edge in edges):
                continue

            edges.append(
                AssetGraphEdge(
                    id=row.id,
                    source=row.source_asset_id,
                    target=row.target_asset_id,
                    relationship_type=row.relationship_type,
                    confidence=row.confidence,
                    review_status=row.review_status,
                    source_document_id=row.source_document_id,
                    evidence_region_id=row.evidence_region_id,
                )
            )
            next_frontier.update({row.source_asset_id, row.target_asset_id})

        missing_ids = next_frontier - set(nodes)
        if missing_ids:
            related = list((await db.scalars(select(Asset).where(Asset.id.in_(missing_ids)))).all())
            for item in related:
                nodes[item.id] = AssetGraphNode(
                    id=item.id,
                    label=f"{item.asset_tag} — {item.name}",
                    node_type="asset",
                    metadata={"asset_type": item.asset_type, "status": item.status},
                )

        visited.update(frontier)
        frontier = next_frontier - visited

    return AssetGraphResponse(
        root_asset_id=asset.id,
        nodes=list(nodes.values()),
        edges=edges,
    )


async def build_asset_timeline(
    db: AsyncSession,
    *,
    asset: Asset,
    limit: int = 100,
) -> AssetTimelineResponse:
    items: list[AssetTimelineItem] = []

    queries = list(
        (
            await db.scalars(
                select(Query).where(
                    Query.site_id == asset.site_id,
                    Query.context_asset_ids.contains([asset.id]),
                )
            )
        ).all()
    )
    for row in queries:
        items.append(
            AssetTimelineItem(
                id=f"timeline_query_{row.id}",
                event_type="query",
                title=row.question,
                occurred_at=row.created_at,
                status=row.status,
                severity=None,
                source_id=row.id,
                metadata={"mode": row.mode},
            )
        )

    rcas = list((await db.scalars(select(RCACase).where(RCACase.asset_id == asset.id))).all())
    for row in rcas:
        items.append(
            AssetTimelineItem(
                id=f"timeline_rca_{row.id}",
                event_type="rca",
                title=row.title,
                occurred_at=row.created_at,
                status=row.status,
                severity=None,
                source_id=row.id,
                metadata={},
            )
        )

    evaluations = list(
        (
            await db.scalars(
                select(ComplianceEvaluation).where(ComplianceEvaluation.asset_id == asset.id)
            )
        ).all()
    )
    for row in evaluations:
        items.append(
            AssetTimelineItem(
                id=f"timeline_compliance_{row.id}",
                event_type="compliance_evaluation",
                title="Compliance evaluation",
                occurred_at=row.created_at,
                status=row.status,
                severity=None,
                source_id=row.id,
                metadata={"overall_status": row.overall_result},
            )
        )

    cards = list(
        (await db.scalars(select(KnowledgeCard).where(KnowledgeCard.asset_id == asset.id))).all()
    )
    for row in cards:
        items.append(
            AssetTimelineItem(
                id=f"timeline_knowledge_{row.id}",
                event_type="knowledge_card",
                title=row.title,
                occurred_at=row.created_at,
                status=row.status,
                severity=None,
                source_id=row.id,
                metadata={"version": row.version},
            )
        )

    items.sort(key=lambda item: item.occurred_at, reverse=True)
    return AssetTimelineResponse(asset_id=asset.id, items=items[:limit])


async def list_asset_aliases(
    db: AsyncSession,
    *,
    asset_id: str,
) -> list[AssetAlias]:
    return list(
        (
            await db.scalars(
                select(AssetAlias).where(AssetAlias.asset_id == asset_id).order_by(AssetAlias.alias)
            )
        ).all()
    )
