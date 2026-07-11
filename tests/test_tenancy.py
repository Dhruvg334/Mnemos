import pytest


@pytest.mark.asyncio
async def test_north_user_cannot_read_south_asset(client, north_token):
    response = await client.get(
        "/api/v1/assets/ast_p117_s",
        headers={"Authorization": f"Bearer {north_token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_list_both_sites(client, admin_token):
    response = await client.get(
        "/api/v1/sites",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["data"]} == {"site_north", "site_south"}
