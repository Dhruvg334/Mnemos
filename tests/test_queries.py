import pytest


async def _create_and_get(client, token, payload):
    accepted = await client.post(
        "/api/v1/queries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 202
    query_id = accepted.json()["data"]["id"]
    return await client.get(
        f"/api/v1/queries/{query_id}",
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.mark.asyncio
async def test_p117_query_returns_citations(client, north_token):
    response = await _create_and_get(
        client,
        north_token,
        {
            "site_id": "site_north",
            "question": "Why has P-117 repeatedly failed?",
            "context": {"asset_ids": ["ast_p117_n"], "document_ids": []},
            "mode": "investigation",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "succeeded"
    assert len(data["citations"]) >= 2
    assert "missing vibration spectrum" in " ".join(data["missing_evidence"]).lower()


@pytest.mark.asyncio
async def test_unsupported_question_abstains(client, north_token):
    response = await _create_and_get(
        client,
        north_token,
        {
            "site_id": "site_north",
            "question": "Who approved the January work order?",
            "context": {"asset_ids": [], "document_ids": []},
            "mode": "general",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "partially_succeeded"
    assert data["confidence_label"] == "low"
