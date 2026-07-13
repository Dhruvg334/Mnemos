from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Mnemos API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./mnemos.db"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "mnemos"
    s3_secret_key: str = "mnemos-secret"
    s3_bucket: str = "mnemos-documents"
    s3_region: str = "us-east-1"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: list[str] = ["http://localhost:3000"]
    mock_agent_enabled: bool = True
    agent_gateway_mode: str = "mock"
    agent_service_url: str = "http://agent-service:8100"
    agent_service_timeout_seconds: float = 30.0
    agent_service_api_key: str | None = None
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
