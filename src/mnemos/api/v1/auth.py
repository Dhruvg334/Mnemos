from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.core.security import create_access_token
from mnemos.models import User
from mnemos.schemas.auth import DevLoginRequest, TokenResponse, UserResponse
from mnemos.schemas.common import Envelope, Meta

router = APIRouter(tags=["auth"])


@router.post("/auth/dev-login", response_model=Envelope[TokenResponse])
async def dev_login(
    payload: DevLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Envelope[TokenResponse]:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        raise AppError("NOT_FOUND", "Development user not found.", 404)
    token = create_access_token(user.id)
    return Envelope(
        data=TokenResponse(access_token=token),
        meta=Meta(request_id=request.state.request_id),
    )


@router.get("/me", response_model=Envelope[UserResponse])
async def me(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Envelope[UserResponse]:
    return Envelope(
        data=UserResponse.model_validate(principal.user),
        meta=Meta(request_id=request.state.request_id),
    )
