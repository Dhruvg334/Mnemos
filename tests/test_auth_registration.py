from sqlalchemy import select

from mnemos.models import Membership, User
from tests.conftest import TestSession


async def test_registration_activates_account_and_returns_session(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Asha Raman",
            "organisation_name": "River Process Works",
            "email": "asha@example.com",
            "password": "StrongPass!2026",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]

    async with TestSession() as db:
        user = await db.scalar(select(User).where(User.email == "asha@example.com"))
        assert user is not None
        assert user.is_active is True
        membership = await db.scalar(select(Membership).where(Membership.user_id == user.id))
        assert membership is not None
        assert membership.role == "organisation_admin"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "asha@example.com", "password": "StrongPass!2026"},
    )
    assert login.status_code == 200


async def test_registration_rejects_existing_email_with_wrong_password(client):
    payload = {
        "full_name": "Asha Raman",
        "organisation_name": "River Process Works",
        "email": "duplicate@example.com",
        "password": "StrongPass!2026",
    }
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    payload["password"] = "DifferentPass!2026"
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_email_verification_routes_are_not_registered(client):
    verify = await client.post("/api/v1/auth/verify-email", json={"token": "x" * 48})
    resend = await client.post(
        "/api/v1/auth/resend-verification",
        json={"email": "asha@example.com"},
    )
    assert verify.status_code == 404
    assert resend.status_code == 404
