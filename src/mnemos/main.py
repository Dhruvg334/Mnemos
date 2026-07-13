from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mnemos.api.v1 import assets, audit, auth, compliance, documents, health, ingestion, knowledge, queries, rcas, sites
from mnemos.core.config import settings
from mnemos.core.db import close_database
from mnemos.core.errors import (
    AppError,
    app_error_handler,
    unexpected_error_handler,
)
from mnemos.core.logging import configure_logging
from mnemos.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from mnemos.core.rate_limit import close_rate_limit_client

configure_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.expose_api_docs else None,
    redoc_url="/redoc" if settings.expose_api_docs else None,
    openapi_url="/openapi.json" if settings.expose_api_docs else None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
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



@app.on_event("shutdown")
async def shutdown_resources() -> None:
    await close_rate_limit_client()
    await close_database()
