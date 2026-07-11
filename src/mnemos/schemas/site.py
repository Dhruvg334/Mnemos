from mnemos.schemas.common import ORMModel


class SiteResponse(ORMModel):
    id: str
    organisation_id: str
    name: str
    code: str
    timezone: str
