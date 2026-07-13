async def test_unknown_fields_rejected(client, north_token):
    response = await client.post("/api/v1/queries",
        headers={"Authorization": f"Bearer {north_token}"},
        json={"site_id":"site_north","question":"Why did P-117 fail?","unexpected":"x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

async def test_control_character_rejected(client, north_token):
    response = await client.post("/api/v1/queries",
        headers={"Authorization": f"Bearer {north_token}"},
        json={"site_id":"site_north","question":"Why did P-117 fail?\u0000"})
    assert response.status_code == 422

async def test_cross_site_context_rejected(client, north_token):
    response = await client.post("/api/v1/queries",
        headers={"Authorization": f"Bearer {north_token}"},
        json={"site_id":"site_north","question":"Investigate selected asset",
              "context":{"asset_ids":["ast_p117_s"]}})
    assert response.status_code == 422

async def test_invalid_token_standard_error(client):
    response = await client.get("/api/v1/me", headers={"Authorization":"Bearer invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers["www-authenticate"] == "Bearer"

async def test_missing_route_standard_error(client):
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
