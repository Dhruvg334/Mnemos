from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mnemos.api.v1 import assets, audit, auth, compliance, documents, health, ingestion, knowledge, queries, rcas, sites
from mnemos.core.config import settings
from mnemos.core.errors import AppError, app_error_handler
from mnemos.core.middleware import RequestIdMiddleware
from mnemos.core.rate_limit import close_rate_limit_client

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)

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
