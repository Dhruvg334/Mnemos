from functools import lru_cache
import json
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Mnemos API"
    app_version: str = "0.1.0"
    expose_api_docs: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./mnemos.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1800
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "mnemos"
    s3_secret_key: str = "mnemos-secret"
    s3_bucket: str = "mnemos-documents"
    s3_region: str = "us-east-1"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    jwt_issuer: str = "mnemos-api"
    jwt_audience: str = "mnemos-client"
    refresh_token_expire_days: int = 7
    frontend_base_url: str = "http://localhost:3000"
    password_min_length: int = 12
    login_lock_threshold: int = 5
    login_lock_minutes: int = 15
    dev_login_enabled: bool = True
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    mock_agent_enabled: bool = True
    agent_gateway_mode: str = "mock"
    agent_service_url: str = "http://agent-service:8100"
    agent_service_timeout_seconds: float = 30.0
    agent_service_api_key: str | None = None
    ingestion_gateway_mode: str = "mock"
    ingestion_service_url: str = "http://agent-service:8100"
    ingestion_service_timeout_seconds: float = 60.0
    ingestion_service_api_key: str | None = None
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_login_requests: int = 8
    rate_limit_login_window_seconds: int = 300
    rate_limit_fail_closed: bool = False
    audit_page_size_max: int = 100
    upstream_retry_attempts: int = 3
    upstream_retry_base_delay_seconds: float = 0.25
    idempotency_key_max_length: int = 128
    idempotency_ttl_hours: int = 24
    query_max_retry_attempts: int = 2
    query_dispatch_mode: str = "background"
    worker_poll_interval_seconds: float = 2.0
    ingestion_max_retry_attempts: int = 2
    security_headers_enabled: bool = True
    max_request_body_bytes: int = 2_000_000
    external_health_checks_enabled: bool = True
    tool_health_failure_rate_threshold: float = 0.25
    tool_health_p95_latency_ms: float = 5_000.0
    max_upload_size_bytes: int = 52_428_800
    upload_session_expire_minutes: int = 15
    allowed_upload_mime_types: Annotated[list[str], NoDecode] = [
        "application/pdf",
        "text/markdown",
        "text/plain",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    # Neo4j Graph Database
    neo4j_enabled: bool = True
    neo4j_startup_required: bool = False
    neo4j_required_for_readiness: bool = False
    neo4j_connect_timeout_seconds: float = 5.0
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_max_connection_pool_size: int = 50

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value):
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+asyncpg://" + value.removeprefix("postgres://")
            if value.startswith("postgresql://"):
                return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    @field_validator("cors_origins", "allowed_upload_mime_types", mode="before")
    @classmethod
    def parse_string_list(cls, value):
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("["):
            decoded = json.loads(raw)
            if not isinstance(decoded, list) or not all(isinstance(item, str) for item in decoded):
                raise ValueError("Expected a JSON array of strings")
            return [item.strip() for item in decoded if item.strip()]
        return [item.strip() for item in raw.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_secure_configuration(self):
        if self.app_env.lower() in {"production", "prod"}:
            self.dev_login_enabled = False
            self.expose_api_docs = False
            self.rate_limit_fail_closed = True
            if self.jwt_secret in {"change-me", "test-secret"} or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be strong in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
        if self.query_dispatch_mode not in {"background", "worker"}:
            raise ValueError("QUERY_DISPATCH_MODE must be background or worker")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
