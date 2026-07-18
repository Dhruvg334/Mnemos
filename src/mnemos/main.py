from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from mnemos.agentic.runtime.api.approvals import create_approval_router
from mnemos.agentic.runtime.approval_queue import DurableApprovalQueue
from mnemos.agentic.runtime.otel import _OTEL_AVAILABLE, get_tracer
from mnemos.api.v1 import (
    assets,
    audit,
    auth,
    compliance,
    documents,
    health,
    ingestion,
    knowledge,
    queries,
    rcas,
    sites,
)
from mnemos.core.config import settings
from mnemos.core.db import SessionLocal, close_database
from mnemos.core.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from mnemos.core.logging import configure_logging
from mnemos.core.middleware import (
    RequestIdMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from mnemos.core.neo4j import close_neo4j, init_neo4j
from mnemos.core.rate_limit import close_rate_limit_client
from mnemos.services.query_execution import resume_query_after_approval

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Own startup and shutdown resources without deprecated event hooks."""
    await init_neo4j()
    _ = get_tracer()

    if _OTEL_AVAILABLE:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception:
            pass
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            SQLAlchemyInstrumentor().instrument()
        except Exception:
            pass

    try:
        yield
    finally:
        await close_neo4j()
        await close_rate_limit_client()
        await close_database()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.expose_api_docs else None,
    redoc_url="/redoc" if settings.expose_api_docs else None,
    openapi_url="/openapi.json" if settings.expose_api_docs else None,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(sites.router, prefix=settings.api_v1_prefix)
app.include_router(assets.router, prefix=settings.api_v1_prefix)
app.include_router(documents.router, prefix=settings.api_v1_prefix)
app.include_router(queries.router, prefix=settings.api_v1_prefix)
app.include_router(rcas.router, prefix=settings.api_v1_prefix)
app.include_router(compliance.router, prefix=settings.api_v1_prefix)
app.include_router(knowledge.router, prefix=settings.api_v1_prefix)
app.include_router(ingestion.router, prefix=settings.api_v1_prefix)
app.include_router(audit.router, prefix=settings.api_v1_prefix)

_approval_queue = DurableApprovalQueue(session_factory=SessionLocal)
app.include_router(
    create_approval_router(
        _approval_queue,
        resume_callback=resume_query_after_approval,
    ),
    prefix=f"{settings.api_v1_prefix}/approvals",
)
