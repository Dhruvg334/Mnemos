import logging
from typing import Any

from fastapi import Request
from fastapi.responses import ORJSONResponse


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable


async def app_error_handler(request: Request, exc: AppError) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "retryable": exc.retryable,
            },
            "meta": {
                "request_id": getattr(request.state, "request_id", None),
                "api_version": "v1",
            },
        },
    )



logger = logging.getLogger("mnemos.errors")


async def unexpected_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "request.unhandled_error",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
        },
    )
    return ORJSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The request could not be completed.",
                "details": {},
                "retryable": False,
            },
            "meta": {"request_id": request_id, "api_version": "v1"},
        },
    )
