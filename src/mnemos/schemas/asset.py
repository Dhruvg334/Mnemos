from mnemos.schemas.common import ORMModel


class AssetResponse(ORMModel):
    id: str
    site_id: str
    asset_tag: str
    name: str
    asset_type: str
    status: str
