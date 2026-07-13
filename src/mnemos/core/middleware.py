from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from mnemos.core.config import settings

logger = logging.getLogger("mnemos.http")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
        started = time.perf_counter()

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request.completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if settings.security_headers_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            response.headers["Cross-Origin-Resource-Policy"] = "same-site"
            if request.url.scheme == "https":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from mnemos.core.errors import AppError

        raw = request.headers.get("content-length")
        if raw is not None:
            try:
                size = int(raw)
            except ValueError as exc:
                raise AppError(
                    "INVALID_CONTENT_LENGTH", "Invalid Content-Length header.", 400
                ) from exc
            if size < 0:
                raise AppError("INVALID_CONTENT_LENGTH", "Invalid Content-Length header.", 400)
            if size > settings.max_request_body_bytes:
                raise AppError(
                    "REQUEST_TOO_LARGE",
                    "Request body exceeds the configured limit.",
                    413,
                    details={"max_request_body_bytes": settings.max_request_body_bytes},
                )
        return await call_next(request)
