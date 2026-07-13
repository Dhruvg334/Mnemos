from mnemos.core.config import settings
from mnemos.integrations.ingestion.base import IngestionGateway
from mnemos.integrations.ingestion.http import HttpIngestionGateway
from mnemos.integrations.ingestion.mock import MockIngestionGateway


def get_ingestion_gateway() -> IngestionGateway:
    if settings.ingestion_gateway_mode == "http":
        return HttpIngestionGateway()
    return MockIngestionGateway()
