import pytest


@pytest.mark.asyncio
async def test_health_endpoints(client):
    live = await client.get("/health/live")
    ready = await client.get("/health/ready")
    assert live.status_code == 200
    assert ready.status_code == 200
    assert live.json() == {"status": "healthy"}
