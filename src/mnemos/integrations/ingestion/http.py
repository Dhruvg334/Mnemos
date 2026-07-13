import httpx

from mnemos.core.config import settings
from mnemos.core.errors import AppError
from mnemos.schemas.ingestion import IngestionRequest, IngestionResult


class HttpIngestionGateway:
    name = "http"

    async def ingest_document(self, request: IngestionRequest) -> IngestionResult:
        headers = {"Content-Type": "application/json"}
        if settings.ingestion_service_api_key:
            headers["Authorization"] = f"Bearer {settings.ingestion_service_api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=settings.ingestion_service_timeout_seconds
            ) as client:
                response = await client.post(
                    f"{settings.ingestion_service_url.rstrip('/')}/v1/documents/ingest",
                    json=request.model_dump(mode="json"),
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AppError(
                "UPSTREAM_TIMEOUT",
                "Ingestion service timed out.",
                504,
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AppError(
                "INGESTION_FAILED",
                "Ingestion service returned an error.",
                502,
                details={"status_code": exc.response.status_code},
                retryable=exc.response.status_code >= 500,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                "INGESTION_FAILED",
                "Ingestion service is unavailable.",
                502,
                retryable=True,
            ) from exc

        try:
            return IngestionResult.model_validate(response.json())
        except Exception as exc:
            raise AppError(
                "INGESTION_FAILED",
                "Ingestion service returned an invalid response.",
                502,
            ) from exc
