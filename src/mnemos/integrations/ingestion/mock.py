from mnemos.schemas.ingestion import IngestionRequest, IngestionResult


class MockIngestionGateway:
    name = "mock"

    async def ingest_document(self, request: IngestionRequest) -> IngestionResult:
        return IngestionResult(
            run_id=request.run_id,
            document_id=request.document_id,
            document_version=request.document_version,
            status="succeeded",
            chunks_created=12,
            entities_created=4,
            relationships_created=5,
            warnings=[],
            pipeline_version="mock-ingestion-1",
        )
