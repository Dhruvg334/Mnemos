from typing import Protocol

from mnemos.schemas.ingestion import IngestionRequest, IngestionResult


class IngestionGateway(Protocol):
    name: str

    async def ingest_document(self, request: IngestionRequest) -> IngestionResult: ...
