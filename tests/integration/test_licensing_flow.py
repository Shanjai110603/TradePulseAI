import os
import time
import tempfile
from pathlib import Path
import pytest
from master_control_panel.database import MasterDatabase, hash_password, verify_password
from core.licensing.client import LicenseClient


@pytest.fixture
def temp_mcp_db():
    """Provides a fresh isolated MasterDatabase in a temporary directory."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test_mcp.db"
        db = MasterDatabase(db_path=db_path)
        yield db


def test_admin_password_pbkdf2_hashing(temp_mcp_db):
    """Verify that admin passwords use PBKDF2-HMAC-SHA256 with random salt."""
    raw_pwd = "TradePulseAdmin2026!"
    hashed = hash_password(raw_pwd)

    # Verify format pbkdf2:sha256:iterations$salt$hash
    assert hashed.startswith("pbkdf2:sha256:100000$")
    parts = hashed.split("$")
    assert len(parts) == 3

    # Verify password verification
    assert verify_password(hashed, raw_pwd) is True
    assert verify_password(hashed, "WrongPassword123") is False

    # Verify default seeded admin account
    assert temp_mcp_db.verify_admin("admin", "adminPassword123!") is True
    assert temp_mcp_db.verify_admin("admin", "wrong") is False


def test_license_lifecycle_management(temp_mcp_db):
    """Verify end-to-end license generation, binding, status toggle, and deletion."""
    # 1. Create 1-year personal subscription key
    lic = temp_mcp_db.create_license(
        customer_name="Test Trader",
        duration_days=365,
        max_devices=1
    )
    assert lic is not None
    lic_key = lic["license_key"]
    assert lic_key.startswith("TP-PERS-")
    assert lic["customer_name"] == "Test Trader"
    assert lic["status"] == "ACTIVE"
    assert lic["bound_hwids"] == []

    # 2. Bind HWID on client activation
    test_hwid = "TEST-HWID-AA-BB-CC-DD-EE-FF"
    activated, msg, lic_bound = temp_mcp_db.validate_and_bind_license(
        license_key=lic_key,
        hwid=test_hwid,
        system_info={"hostname": "Test-PC", "os_version": "Windows 11"}
    )
    assert activated is True
    assert test_hwid in lic_bound["bound_hwids"]

    # 3. Attempt activation from second device should fail (single-system enforcement)
    second_hwid = "TEST-HWID-99-88-77-66-55-44"
    act_second, msg_second, _ = temp_mcp_db.validate_and_bind_license(
        license_key=lic_key,
        hwid=second_hwid,
        system_info={"hostname": "Second-PC", "os_version": "Windows 11"}
    )
    assert act_second is False
    assert "unauthorized" in msg_second.lower() or "locked" in msg_second.lower()

    # 4. Toggle status to SUSPENDED
    new_status = temp_mcp_db.toggle_license_status(lic_key, "SUSPENDED")
    assert new_status == "SUSPENDED"
    lic_suspended = temp_mcp_db.get_license(lic_key)
    assert lic_suspended["status"] == "SUSPENDED"

    # 5. Activation while suspended should fail
    act_suspended, msg_sus, _ = temp_mcp_db.validate_and_bind_license(lic_key, test_hwid, {})
    assert act_suspended is False
    assert "suspended" in msg_sus.lower()

    # 6. Reset HWID for re-binding
    reset = temp_mcp_db.reset_hwid(lic_key)
    assert reset is True
    assert temp_mcp_db.get_license(lic_key)["bound_hwids"] == []


def test_license_client_offline_grace_period():
    """Verify that the client enforces a 48-hour maximum offline grace period."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        cache_file = Path(tmpdir) / "test_lic_cache.dat"
        client = LicenseClient(cache_path=cache_file)

        # 1. Valid fresh cache
        now = time.time()
        client.license_key = "TP-PERS-TEST-KEY"
        client.customer_name = "Offline User"
        client.expires_at = (time.time() + 86400 * 30)
        client.last_verified_online_ts = now
        client.is_licensed = True
        client.save_cached_license()

        is_valid, msg = client.validate_license("TP-PERS-TEST-KEY", "http://127.0.0.1:59999")
        assert is_valid is True
        assert "offline mode" in msg.lower()

        # 2. Stale cache exceeding 48-hour maximum grace period
        client.last_verified_online_ts = now - (50 * 3600)  # 50 hours ago
        client.save_cached_license()

        is_valid_stale, msg_stale = client.validate_license("TP-PERS-TEST-KEY", "http://127.0.0.1:59999")
        assert is_valid_stale is False
        assert "grace period" in msg_stale.lower()


def test_license_client_revocation_callback():
    """Verify that revocation callback triggers on license invalidation."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        cache_file = Path(tmpdir) / "test_revocation.dat"
        client = LicenseClient(cache_path=cache_file)
        client.license_key = "TP-PERS-TEST-KEY"
        client.is_licensed = True
        client.save_cached_license()

        revocation_events = []
        def on_revoked(reason):
            revocation_events.append(reason)

        client.set_revocation_callback(on_revoked)

        # Trigger client revocation handler
        client.revoke("Test Administrative Revocation")
        assert len(revocation_events) == 1
        assert "Test Administrative Revocation" in revocation_events[0]
        assert client.is_licensed is False
        assert cache_file.exists() is False  # Cache cleared
