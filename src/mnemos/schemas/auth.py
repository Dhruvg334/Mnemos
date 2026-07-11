from pydantic import BaseModel, EmailStr

from mnemos.schemas.common import ORMModel


class DevLoginRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(ORMModel):
    id: str
    email: str
    full_name: str
    is_active: bool
