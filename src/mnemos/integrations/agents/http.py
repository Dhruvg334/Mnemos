import httpx

from mnemos.core.config import settings
from mnemos.core.errors import AppError
from mnemos.core.resilience import retry_async
from mnemos.schemas.agent import AgentQueryRequest, AgentQueryResult


class HttpAgentGateway:
    name = "http"

    async def execute_query(self, request: AgentQueryRequest) -> AgentQueryResult:
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": request.run_id,
        }
        api_key = settings.agent_service_api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async def invoke() -> AgentQueryResult:
            try:
                async with httpx.AsyncClient(
                    timeout=settings.agent_service_timeout_seconds
                ) as client:
                    response = await client.post(
                        f"{settings.agent_service_url.rstrip('/')}/v1/queries/execute",
                        json=request.model_dump(mode="json"),
                        headers=headers,
                    )
                    response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise AppError(
                    "UPSTREAM_TIMEOUT",
                    "Upstream service timed out.",
                    504,
                    retryable=True,
                ) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                raise AppError(
                    "AGENT_EXECUTION_FAILED",
                    "Upstream service returned an error.",
                    502,
                    details={"upstream_status": status},
                    retryable=status >= 500 or status == 429,
                ) from exc
            except httpx.HTTPError as exc:
                raise AppError(
                    "AGENT_EXECUTION_FAILED",
                    "Upstream service is unavailable.",
                    502,
                    retryable=True,
                ) from exc

            try:
                return AgentQueryResult.model_validate(response.json())
            except (ValueError, TypeError) as exc:
                raise AppError(
                    "AGENT_EXECUTION_FAILED",
                    "Upstream service returned an invalid response.",
                    502,
                    retryable=False,
                ) from exc

        result, _ = await retry_async(
            invoke,
            attempts=settings.upstream_retry_attempts,
            base_delay_seconds=settings.upstream_retry_base_delay_seconds,
        )
        return result
