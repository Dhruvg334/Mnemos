from __future__ import annotations
import hashlib, secrets, uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from mnemos.core.config import settings

_passwords = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(password: str) -> str:
    return _passwords.hash(password)

def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        _passwords.hash(password)
        return False
    return _passwords.verify(password, password_hash)

def validate_password_strength(password: str) -> None:
    if len(password) < settings.password_min_length:
        raise ValueError("Password is too short")
    checks = [any(c.islower() for c in password), any(c.isupper() for c in password),
              any(c.isdigit() for c in password), any(not c.isalnum() for c in password)]
    if not all(checks):
        raise ValueError("Password must include upper, lower, number and symbol")

def create_access_token(subject: str, *, token_version: int = 0, claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject, "iat": int(now.timestamp()), "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
        "jti": uuid.uuid4().hex, "typ": "access", "ver": token_version,
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                             audience=settings.jwt_audience, issuer=settings.jwt_issuer,
                             options={"require_sub": True, "require_exp": True, "require_iat": True})
    except JWTError as exc:
        raise ValueError("Invalid access token") from exc
    if payload.get("typ") != "access" or not isinstance(payload.get("ver"), int):
        raise ValueError("Invalid access token")
    return payload

def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
