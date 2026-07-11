import pytest


@pytest.mark.asyncio
async def test_p117_query_returns_citations(client, north_token):
    response = await client.post(
        "/api/v1/queries",
        json={
            "site_id": "site_north",
            "question": "Why has P-117 repeatedly failed?",
            "context": {"asset_ids": ["ast_p117_n"], "document_ids": []},
            "mode": "investigation",
        },
        headers={"Authorization": f"Bearer {north_token}"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "succeeded"
    assert len(data["citations"]) >= 2
    assert "missing vibration spectrum" in " ".join(data["missing_evidence"]).lower()


@pytest.mark.asyncio
async def test_unsupported_question_abstains(client, north_token):
    response = await client.post(
        "/api/v1/queries",
        json={
            "site_id": "site_north",
            "question": "Who approved the January work order?",
            "context": {"asset_ids": [], "document_ids": []},
            "mode": "general",
        },
        headers={"Authorization": f"Bearer {north_token}"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "partially_succeeded"
    assert data["confidence_label"] == "low"
