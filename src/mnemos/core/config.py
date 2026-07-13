from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    password_min_length: int = 12
    login_lock_threshold: int = 5
    login_lock_minutes: int = 15
    dev_login_enabled: bool = True
    cors_origins: list[str] = ["http://localhost:3000"]
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
    ingestion_max_retry_attempts: int = 2
    security_headers_enabled: bool = True
    max_request_body_bytes: int = 2_000_000
    max_upload_size_bytes: int = 52_428_800
    upload_session_expire_minutes: int = 15
    allowed_upload_mime_types: list[str] = [
        "application/pdf", "text/markdown", "text/plain", "text/csv",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", "allowed_upload_mime_types", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
