import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.database import init_db


@pytest.mark.asyncio
async def test_health_endpoint():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/admin/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "database" in data
        assert "market_data_provider" in data


@pytest.mark.asyncio
async def test_auth_and_pattern_creation_flow():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register new test user
        reg_resp = await ac.post("/api/v1/auth/register", json={
            "email": "tester_quant@tradepulse.ai",
            "password": "strongpassword123",
            "full_name": "Quant Tester"
        })
        if reg_resp.status_code == 400:
            # Already exists, login instead
            login_resp = await ac.post("/api/v1/auth/login", data={
                "username": "tester_quant@tradepulse.ai",
                "password": "strongpassword123"
            })
            token = login_resp.json()["access_token"]
        else:
            token = reg_resp.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get current user
        me_resp = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "tester_quant@tradepulse.ai"

        # 3. Create pattern
        pat_resp = await ac.post("/api/v1/patterns", headers=headers, json={
            "name": "Integration Test Pattern 14",
            "description": "Integration test breakout",
            "market_id": "digital_options",
            "direction": "DOWN",
            "timeframe": "1M",
            "assets_config": ["EUR/USD"],
            "rules_config": {
                "operator": "AND",
                "conditions": [
                    {
                        "type": "pattern_type_14",
                        "params": {"bullish_count": 2, "confirmation": "close_below"}
                    }
                ]
            },
            "is_active": True
        })
        assert pat_resp.status_code == 201
        pattern_data = pat_resp.json()
        assert pattern_data["name"] == "Integration Test Pattern 14"
        pattern_id = pattern_data["id"]

        # 4. Generate Telegram linking code
        link_resp = await ac.post("/api/v1/telegram/link-code", headers=headers)
        assert link_resp.status_code == 200
        code = link_resp.json()["code"]
        assert len(code) == 6

        # 5. Simulate Telegram bot /link command
        webhook_resp = await ac.post("/api/v1/telegram/webhook", json={
            "message": {
                "chat": {"id": 123456789},
                "from": {"id": 987654321, "username": "quant_trader", "first_name": "Trader"},
                "text": f"/link {code}"
            }
        })
        assert webhook_resp.status_code == 200

        # 6. Verify Telegram status
        status_resp = await ac.get("/api/v1/telegram/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["is_linked"] is True

        # 7. Run backtest on pattern
        bt_resp = await ac.post("/api/v1/backtests/run", headers=headers, json={
            "pattern_id": pattern_id,
            "market_id": "digital_options",
            "asset_symbol": "EUR/USD",
            "timeframe": "1M",
            "candle_count": 100
        })
        assert bt_resp.status_code == 200
        bt_data = bt_resp.json()
        assert bt_data["status"] == "COMPLETED"
        assert "win_rate_percentage" in bt_data
