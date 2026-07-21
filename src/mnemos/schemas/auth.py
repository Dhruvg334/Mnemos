from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from mnemos.core.security import validate_password_strength
from mnemos.schemas.common import ORMModel


class DevLoginRequest(BaseModel):
    email: EmailStr
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    organisation_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    model_config = {"extra": "forbid", "str_strip_whitespace": True}

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)
    model_config = {"extra": "forbid"}


class LogoutRequest(RefreshRequest):
    pass


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)
    model_config = {"extra": "forbid"}

    @field_validator("new_password")
    @classmethod
    def strong(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class UserResponse(ORMModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    email_verified_at: datetime | None = None
