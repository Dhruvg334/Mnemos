from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.core.rate_limit import enforce_rate_limit
from mnemos.core.security import decode_access_token
from mnemos.models import Membership, User

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    memberships: list[Membership]


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise AppError("UNAUTHENTICATED", "Authentication required.", 401)

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise AppError("UNAUTHENTICATED", "Invalid access token.", 401) from exc

    user_id = payload.get("sub")
    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise AppError("UNAUTHENTICATED", "User is not active.", 401)
    if payload.get("ver") != user.token_version:
        raise AppError("UNAUTHENTICATED", "Access token has been revoked.", 401)
    await enforce_rate_limit(request, user.id)

    memberships = list(
        (await db.scalars(select(Membership).where(Membership.user_id == user.id))).all()
    )
    return Principal(user=user, memberships=memberships)


def require_site_access(principal: Principal, site_id: str) -> Membership:
    for membership in principal.memberships:
        if membership.site_id is None or membership.site_id == site_id:
            return membership
    raise AppError("FORBIDDEN", "Site access denied.", 403)


def require_site_role(
    principal: Principal,
    site_id: str,
    allowed_roles: set[str],
) -> Membership:
    membership = require_site_access(principal, site_id)
    if membership.role not in allowed_roles:
        raise AppError(
            "FORBIDDEN",
            "Your role does not permit this action.",
            403,
            details={"required_roles": sorted(allowed_roles), "current_role": membership.role},
        )
    return membership


async def rate_limited_principal(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Principal:
    await enforce_rate_limit(request, principal.user.id)
    return principal


def require_admin(principal: Principal) -> None:
    allowed = {"platform_admin", "organisation_admin", "site_admin"}
    if not any(membership.role in allowed for membership in principal.memberships):
        raise AppError("FORBIDDEN", "Administrator access required.", 403)
