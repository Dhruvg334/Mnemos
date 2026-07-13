import httpx

from mnemos.core.config import settings
from mnemos.core.errors import AppError
from mnemos.schemas.agent import AgentQueryRequest, AgentQueryResult


class HttpAgentGateway:
    name = "http"

    async def execute_query(self, request: AgentQueryRequest) -> AgentQueryResult:
        headers = {"Content-Type": "application/json"}
        if settings.agent_service_api_key:
            headers["Authorization"] = f"Bearer {settings.agent_service_api_key}"
        try:
            async with httpx.AsyncClient(timeout=settings.agent_service_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.agent_service_url.rstrip('/')}/v1/queries/execute",
                    json=request.model_dump(mode="json"),
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AppError("UPSTREAM_TIMEOUT", "Agent service timed out.", 504, retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            raise AppError(
                "AGENT_EXECUTION_FAILED",
                "Agent service returned an error.",
                502,
                details={"upstream_status": exc.response.status_code},
                retryable=retryable,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                "AGENT_EXECUTION_FAILED",
                "Agent service is unavailable.",
                502,
                retryable=True,
            ) from exc
        try:
            return AgentQueryResult.model_validate(response.json())
        except (ValueError, TypeError) as exc:
            raise AppError(
                "AGENT_RESPONSE_INVALID",
                "Agent service returned an invalid response.",
                502,
                retryable=False,
            ) from exc
