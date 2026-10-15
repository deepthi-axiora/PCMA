import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_health_and_readiness_endpoints():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        health_data = health_resp.json()
        assert health_data["status"] == "healthy"
        assert health_data["database"] is True

        readiness_resp = await client.get("/readiness")
        assert readiness_resp.status_code == 200
        readiness_data = readiness_resp.json()
        assert readiness_data["status"] == "ready"
        assert readiness_data["database"] is True
