import logging
from typing import Any
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
logger = logging.getLogger("mnemos.errors")

class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int, *,
                 details: dict[str, Any] | None = None, retryable: bool = False):
        super().__init__(message); self.code=code; self.message=message
        self.status_code=status_code; self.details=details or {}; self.retryable=retryable

def _meta(request: Request):
    return {"request_id": getattr(request.state, "request_id", None), "api_version": "v1"}

async def app_error_handler(request: Request, exc: AppError):
    headers={}
    if exc.status_code == 401: headers["WWW-Authenticate"]="Bearer"
    if exc.status_code == 429 and "retry_after_seconds" in exc.details:
        headers["Retry-After"]=str(exc.details["retry_after_seconds"])
    return ORJSONResponse(status_code=exc.status_code, headers=headers, content={
        "error":{"code":exc.code,"message":exc.message,"details":exc.details,"retryable":exc.retryable},
        "meta":_meta(request)})

async def validation_error_handler(request: Request, exc: RequestValidationError):
    fields=[{"field":".".join(str(x) for x in e.get("loc",[])[1:]),
             "message":e.get("msg","Invalid value"),"type":e.get("type","validation_error")}
            for e in exc.errors()]
    return ORJSONResponse(status_code=422, content={"error":{
        "code":"VALIDATION_ERROR","message":"One or more request fields are invalid.",
        "details":{"fields":fields},"retryable":False},"meta":_meta(request)})

async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return ORJSONResponse(status_code=exc.status_code, content={"error":{
        "code":"NOT_FOUND" if exc.status_code==404 else "HTTP_ERROR",
        "message":"Route not found." if exc.status_code==404 else "Request could not be completed.",
        "details":{},"retryable":False},"meta":_meta(request)})

async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("request.unhandled_error", extra={"request_id":getattr(request.state,"request_id",None),
        "method":request.method,"path":request.url.path,"status_code":500})
    return ORJSONResponse(status_code=500, content={"error":{
        "code":"INTERNAL_ERROR","message":"The request could not be completed.",
        "details":{},"retryable":False},"meta":_meta(request)})
