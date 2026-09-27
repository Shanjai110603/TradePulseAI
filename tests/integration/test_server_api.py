import pytest
from fastapi.testclient import TestClient
from master_control_panel.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_admin_api_requires_auth(client):
    """Verify that unauthenticated requests to /api/v1/admin/* return 401."""
    endpoints = [
        ("GET", "/api/v1/admin/stats"),
        ("GET", "/api/v1/admin/licenses"),
        ("GET", "/api/v1/admin/telemetry"),
        ("POST", "/api/v1/admin/licenses"),
        ("POST", "/api/v1/admin/licenses/DUMMY-KEY/toggle-status"),
        ("POST", "/api/v1/admin/licenses/DUMMY-KEY/extend"),
        ("POST", "/api/v1/admin/licenses/DUMMY-KEY/reset-hwid"),
        ("POST", "/api/v1/admin/licenses/DUMMY-KEY/set-max-devices"),
        ("DELETE", "/api/v1/admin/licenses/DUMMY-KEY"),
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path)
        elif method == "DELETE":
            resp = client.delete(path)
        else:
            resp = client.post(path, json={})
        assert resp.status_code == 401, f"Endpoint {path} did not reject unauthenticated access (got {resp.status_code})"


def test_admin_login_and_authenticated_workflow(client):
    """Verify admin login generates token, grants access to endpoints, and logs out."""
    # 1. Failed login with invalid credentials
    bad_login = client.post("/api/v1/admin/login", json={"username": "admin", "password": "WrongPassword!"})
    assert bad_login.status_code == 401

    # 2. Successful login with default admin credentials
    good_login = client.post("/api/v1/admin/login", json={"username": "admin", "password": "adminPassword123!"})
    assert good_login.status_code == 200
    login_data = good_login.json()
    assert login_data.get("success") is True
    token = login_data.get("token")
    assert token is not None
    assert len(token) >= 32

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Access protected dashboard stats with token
    stats_resp = client.get("/api/v1/admin/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_licenses" in stats
    assert "active_licenses" in stats

    # 4. Create license via authenticated API
    create_resp = client.post("/api/v1/admin/licenses", headers=headers, json={
        "customer_name": "API Test Customer",
        "duration_days": 365,
        "max_devices": 1
    })
    assert create_resp.status_code == 200
    create_data = create_resp.json()
    assert create_data.get("success") is True
    lic_key = create_data["license"]["license_key"]

    # 5. Public validation endpoint (used by client desktop app)
    val_resp = client.post("/api/v1/license/validate", json={
        "license_key": lic_key,
        "hwid": "TEST-SERVER-HWID-001",
        "hostname": "TestNode",
        "os_version": "Windows 11"
    })
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data.get("success") is True

    # 6. Admin Logout invalidates token
    logout_resp = client.post("/api/v1/admin/logout", headers=headers)
    assert logout_resp.status_code == 200

    # 7. Access with logged out token now returns 401
    post_logout_resp = client.get("/api/v1/admin/stats", headers=headers)
    assert post_logout_resp.status_code == 401
