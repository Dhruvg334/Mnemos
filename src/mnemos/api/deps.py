from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.core.db import get_db
from mnemos.core.errors import AppError
from mnemos.core.security import decode_access_token
from mnemos.models import Membership, User

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    memberships: list[Membership]


async def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if credentials is None:
        raise AppError("UNAUTHENTICATED", "Authentication required.", 401)

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise AppError("UNAUTHENTICATED", "Invalid access token.", 401)

    user_id = payload.get("sub")
    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise AppError("UNAUTHENTICATED", "User is not active.", 401)

    memberships = list(
        (
            await db.scalars(
                select(Membership).where(Membership.user_id == user.id)
            )
        ).all()
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
