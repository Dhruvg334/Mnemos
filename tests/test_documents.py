import pytest

@pytest.mark.asyncio
async def test_upload_metadata_validation(client, north_token):
    response = await client.post(
        "/api/v1/documents/upload-session",
        json={
            "site_id": "site_north",
            "filename": "../unsafe.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1280,
            "sha256": "a" * 64,
            "document_type": "work_order",
        },
        headers={"Authorization": f"Bearer {north_token}"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

@pytest.mark.asyncio
async def test_reject_unsupported_upload_type(client, north_token):
    response = await client.post(
        "/api/v1/documents/upload-session",
        json={
            "site_id": "site_north",
            "filename": "payload.exe",
            "mime_type": "application/octet-stream",
            "size_bytes": 1280,
            "sha256": "a" * 64,
            "document_type": "work_order",
        },
        headers={"Authorization": f"Bearer {north_token}"},
    )
    assert response.status_code == 415
