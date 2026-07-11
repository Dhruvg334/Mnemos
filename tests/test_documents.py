import pytest


@pytest.mark.asyncio
async def test_create_document_and_reject_duplicate(client, north_token):
    payload = {
        "site_id": "site_north",
        "filename": "WO-2026-048.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1280,
        "sha256": "a" * 64,
        "document_type": "work_order",
    }
    first = await client.post(
        "/api/v1/documents",
        json=payload,
        headers={"Authorization": f"Bearer {north_token}"},
    )
    assert first.status_code == 201
    assert first.json()["data"]["status"] == "uploaded"

    second = await client.post(
        "/api/v1/documents",
        json=payload,
        headers={"Authorization": f"Bearer {north_token}"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"
