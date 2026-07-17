from sqlalchemy import select

from mnemos.models import Membership, User
from tests.conftest import TestSession


async def test_registration_requires_email_verification(client, monkeypatch):
    captured = {}

    async def capture_delivery(user, raw_token):
        captured["email"] = user.email
        captured["token"] = raw_token

    monkeypatch.setattr(
        "mnemos.api.v1.auth._deliver_verification",
        capture_delivery,
    )

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Raman",
            "organisation_name": "River Process Works",
            "email": "asha@example.com",
            "password": "StrongPass!2026",
        },
    )
    assert response.status_code == 202
    assert response.json()["data"]["verification_required"] is True
    assert captured["email"] == "asha@example.com"

    async with TestSession() as db:
        user = await db.scalar(select(User).where(User.email == "asha@example.com"))
        assert user is not None
        assert user.is_active is False
        membership = await db.scalar(select(Membership).where(Membership.user_id == user.id))
        assert membership is not None
        assert membership.role == "organisation_admin"

    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": captured["token"]},
    )
    assert verify.status_code == 200
    assert verify.json()["data"]["verified"] is True

    async with TestSession() as db:
        user = await db.scalar(select(User).where(User.email == "asha@example.com"))
        assert user.is_active is True
        assert user.email_verified_at is not None
