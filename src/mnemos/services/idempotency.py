from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.core.config import settings
from mnemos.core.errors import AppError
from mnemos.models import IdempotencyRecord


def request_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise AppError("INVALID_IDEMPOTENCY_KEY", "Idempotency-Key is empty.", 400)
    if len(value) > settings.idempotency_key_max_length:
        raise AppError(
            "INVALID_IDEMPOTENCY_KEY",
            "Idempotency-Key is too long.",
            400,
        )
    return value


async def find_idempotent_resource(
    db: AsyncSession,
    *,
    user_id: str,
    operation: str,
    key: str,
    payload_hash: str,
) -> IdempotencyRecord | None:
    record = await db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if record is None:
        return None
    if record.expires_at <= datetime.now(UTC):
        await db.delete(record)
        await db.flush()
        return None
    if record.request_hash != payload_hash:
        raise AppError(
            "IDEMPOTENCY_CONFLICT",
            "The Idempotency-Key was already used with a different request.",
            409,
        )
    return record


async def save_idempotency_record(
    db: AsyncSession,
    *,
    user_id: str,
    organisation_id: str,
    site_id: str | None,
    operation: str,
    key: str,
    payload_hash: str,
    resource_type: str,
    resource_id: str,
    response_status: int,
) -> IdempotencyRecord:
    record = IdempotencyRecord(
        user_id=user_id,
        organisation_id=organisation_id,
        site_id=site_id,
        operation=operation,
        idempotency_key=key,
        request_hash=payload_hash,
        resource_type=resource_type,
        resource_id=resource_id,
        response_status=response_status,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.idempotency_ttl_hours),
    )
    db.add(record)
    await db.flush()
    return record
