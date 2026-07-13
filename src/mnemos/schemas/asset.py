from datetime import datetime


from mnemos.schemas.common import ORMModel, APIModel


class AssetResponse(ORMModel):
    id: str
    site_id: str
    asset_tag: str
    name: str
    asset_type: str
    status: str



class AssetAliasResponse(ORMModel):
    id: str
    site_id: str
    asset_id: str
    alias: str
    normalized_alias: str
    source: str
    confidence: float | None


class AssetRelationshipResponse(ORMModel):
    id: str
    site_id: str
    source_asset_id: str
    target_asset_id: str
    relationship_type: str
    confidence: float | None
    source_document_id: str | None
    evidence_region_id: str | None
    review_status: str
    valid_from: datetime | None
    valid_to: datetime | None


class AssetGraphNode(APIModel):
    id: str
    label: str
    node_type: str
    metadata: dict


class AssetGraphEdge(APIModel):
    id: str
    source: str
    target: str
    relationship_type: str
    confidence: float | None
    review_status: str
    source_document_id: str | None
    evidence_region_id: str | None


class AssetGraphResponse(APIModel):
    root_asset_id: str
    nodes: list[AssetGraphNode]
    edges: list[AssetGraphEdge]


class AssetTimelineItem(APIModel):
    id: str
    event_type: str
    title: str
    occurred_at: datetime
    status: str | None
    severity: str | None
    source_id: str
    metadata: dict


class AssetTimelineResponse(APIModel):
    asset_id: str
    items: list[AssetTimelineItem]
