from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.api.deps import Principal, get_principal
from mnemos.core.config import settings
from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.core.rate_limit import enforce_public_rate_limit
from mnemos.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from mnemos.models import RefreshToken, User
from mnemos.schemas.auth import (
    DevLoginRequest,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from mnemos.schemas.common import Envelope, Meta

router = APIRouter(tags=["auth"])


def _client_identity(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    raw = create_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return TokenResponse(
        access_token=create_access_token(user.id, token_version=user.token_version),
        refresh_token=raw,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/login", response_model=Envelope[TokenResponse])
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await enforce_public_rate_limit(
        request,
        _client_identity(request),
        limit=settings.rate_limit_login_requests,
        window_seconds=settings.rate_limit_login_window_seconds,
    )
    user = await db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None:
        verify_password(payload.password, None)
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)

    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        raise AppError(
            "ACCOUNT_LOCKED", "Account is temporarily locked. Try again later.", 423, retryable=True
        )
    if not user.is_active or not verify_password(payload.password, user.password_hash):
        if user.is_active:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_lock_threshold:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_count = 0
            await db.commit()
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    tokens = await _issue_tokens(db, user)
    await db.commit()
    return Envelope(data=tokens, meta=Meta(request_id=request.state.request_id))


@router.post("/auth/refresh", response_model=Envelope[TokenResponse])
async def refresh(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
        .with_for_update()
    )
    now = datetime.now(UTC)
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise AppError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired.", 401)
    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise AppError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired.", 401)
    token.revoked_at = now
    result = await _issue_tokens(db, user)
    await db.commit()
    return Envelope(data=result, meta=Meta(request_id=request.state.request_id))


@router.post("/auth/logout", response_model=Envelope[dict[str, bool]])
async def logout(payload: LogoutRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(payload.refresh_token)
        )
    )
    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        await db.commit()
    return Envelope(data={"revoked": True}, meta=Meta(request_id=request.state.request_id))


@router.post("/auth/dev-login", response_model=Envelope[TokenResponse])
async def dev_login(payload: DevLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.dev_login_enabled or settings.app_env.lower() in {"production", "prod"}:
        raise AppError("NOT_FOUND", "Route not found.", 404)
    user = await db.scalar(
        select(User).where(User.email == str(payload.email).lower(), User.is_active.is_(True))
    )
    if user is None:
        raise AppError("NOT_FOUND", "Development user not found.", 404)
    return Envelope(
        data=TokenResponse(
            access_token=create_access_token(user.id, token_version=user.token_version),
            expires_in=settings.access_token_expire_minutes * 60,
        ),
        meta=Meta(request_id=request.state.request_id),
    )


@router.post("/auth/change-password", response_model=Envelope[dict[str, bool]])
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    db: AsyncSession = Depends(get_db),
):
    user = principal.user
    if not verify_password(payload.current_password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Current password is incorrect.", 401)
    if verify_password(payload.new_password, user.password_hash):
        raise AppError(
            "VALIDATION_ERROR", "New password must differ from the current password.", 422
        )
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    now = datetime.now(UTC)
    tokens = list(
        (
            await db.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
                )
            )
        ).all()
    )
    for token in tokens:
        token.revoked_at = now
    await db.commit()
    return Envelope(data={"changed": True}, meta=Meta(request_id=request.state.request_id))


@router.get("/me", response_model=Envelope[UserResponse])
async def me(request: Request, principal: Principal = Depends(get_principal)):
    return Envelope(
        data=UserResponse.model_validate(principal.user),
        meta=Meta(request_id=request.state.request_id),
    )
