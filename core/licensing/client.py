"""
TradePulse Client Licensing & Single-System HWID Enforcer
=========================================================
Generates cryptographic machine hardware ID (HWID), verifies active
1-year subscription with the Master Control Panel Server, and syncs
client telemetry (active strategies, bot info, and scanner status).
"""
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("TradePulse.LicensingClient")


def get_system_hwid() -> str:
    """
    Generates a secure, deterministic hardware fingerprint (HWID)
    based on machine UUID, motherboard serial, CPU ID, and OS signature.
    """
    raw_components = []
    
    # 1. Platform / Machine Name
    raw_components.append(platform.node())
    raw_components.append(platform.machine())
    raw_components.append(platform.processor())

    # 2. Windows-Specific Machine GUID / Motherboard Serial
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    raw_components.append(str(guid))
        except Exception:
            pass

        try:
            cmd = "wmic baseboard get serialnumber"
            res = subprocess.check_output(cmd, shell=True, text=True, timeout=2).strip()
            lines = [l.strip() for l in res.splitlines() if l.strip() and "SerialNumber" not in l]
            if lines:
                raw_components.append(lines[0])
        except Exception:
            pass
    else:
        # Linux / MacOS fallback
        try:
            node_uuid = Path("/etc/machine-id")
            if node_uuid.exists():
                raw_components.append(node_uuid.read_text().strip())
        except Exception:
            pass

    combined_str = "||".join(raw_components)
    hwid_hash = hashlib.sha256(combined_str.encode("utf-8")).hexdigest().upper()
    return f"HWID-{hwid_hash[:4]}-{hwid_hash[4:8]}-{hwid_hash[8:12]}-{hwid_hash[12:16]}"


class LicenseClient:
    """Manages client license activation, local cache, and master server telemetry."""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir:
            self.data_dir = data_dir
        else:
            self.data_dir = Path.home() / ".tradepulse"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.license_file = self.data_dir / "personal_license.json"
        
        self.hwid: str = get_system_hwid()
        self.license_key: str = ""
        self.server_url: str = os.getenv("TRADEPULSE_MASTER_SERVER", "http://127.0.0.1:8000").rstrip("/")
        
        self.is_licensed: bool = False
        self.license_data: Dict[str, Any] = {}
        self.last_error_message: str = ""
        self.customer_name: str = ""
        self.expires_at: str = ""
        
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._get_telemetry_callback = None

        self.load_cached_license()

    def set_telemetry_callback(self, cb):
        self._get_telemetry_callback = cb

    def load_cached_license(self):
        if self.license_file.exists():
            try:
                data = json.loads(self.license_file.read_text(encoding="utf-8"))
                self.license_key = data.get("license_key", "")
                self.server_url = data.get("server_url", self.server_url).rstrip("/")
            except Exception as e:
                logger.debug(f"Error loading cached license: {e}")

    def save_cached_license(self):
        try:
            payload = {
                "license_key": self.license_key,
                "server_url": self.server_url,
                "hwid": self.hwid,
                "cached_at": time.time()
            }
            self.license_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Error saving license cache: {e}")

    def validate_license(self, license_key: Optional[str] = None, server_url: Optional[str] = None) -> Tuple[bool, str]:
        """
        Communicates with Master Control Panel to validate 1-year subscription
        and verify that this machine HWID is authorized.
        """
        key_to_check = (license_key or self.license_key).strip()
        if not key_to_check:
            self.is_licensed = False
            self.last_error_message = "No license key configured. Please enter your 1-year subscription key."
            return False, self.last_error_message

        if server_url:
            self.server_url = server_url.rstrip("/")

        endpoint = f"{self.server_url}/api/v1/license/validate"
        telemetry_extra = {}
        if self._get_telemetry_callback:
            try:
                telemetry_extra = self._get_telemetry_callback() or {}
            except Exception:
                pass

        payload = {
            "license_key": key_to_check,
            "hwid": self.hwid,
            "hostname": platform.node(),
            "os_version": f"{platform.system()} {platform.release()}",
            "app_version": "2.0 Personal",
            "bot_token_prefix": telemetry_extra.get("bot_token_prefix", ""),
            "telegram_chat_id": telemetry_extra.get("telegram_chat_id", ""),
            "active_strategies": telemetry_extra.get("active_strategies", []),
            "quotex_logged_in": telemetry_extra.get("quotex_logged_in", False),
            "scanner_active": telemetry_extra.get("scanner_active", False)
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "TradePulse-Personal/2.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                if resp_json.get("success"):
                    self.license_key = key_to_check
                    self.is_licensed = True
                    self.license_data = resp_json.get("license", {})
                    self.customer_name = self.license_data.get("customer_name", "Client")
                    self.expires_at = self.license_data.get("expires_at", "")
                    self.last_error_message = ""
                    self.save_cached_license()
                    logger.info(f"✅ Subscription Active! Verified for {self.customer_name} (HWID: {self.hwid})")
                    return True, "Subscription Active and verified for this machine."
                else:
                    self.is_licensed = False
                    self.last_error_message = resp_json.get("message", "Validation failed")
                    return False, self.last_error_message

        except urllib.error.HTTPError as e:
            try:
                err_json = json.loads(e.read().decode("utf-8"))
                msg = err_json.get("message") or err_json.get("detail") or str(e)
            except Exception:
                msg = f"HTTP Error {e.code}: {e.reason}"
            self.is_licensed = False
            self.last_error_message = msg
            logger.warning(f"🔒 License Validation Denied: {msg}")
            return False, msg

        except Exception as e:
            logger.debug(f"Network error contacting master server: {e}")
            # If server is temporarily unreachable and we already had a cached license
            if self.license_key == key_to_check and self.is_licensed:
                return True, "Active (Offline Cached Mode)"
            self.is_licensed = False
            self.last_error_message = f"Cannot reach Master Server ({self.server_url}). Check connection."
            return False, self.last_error_message

    def start_heartbeat(self):
        if self._running:
            return
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="TradePulse-LicensingHeartbeat")
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        self._running = False

    def _heartbeat_loop(self):
        while self._running:
            time.sleep(25)
            if not self._running:
                break
            if not self.license_key or not self.is_licensed:
                continue

            telemetry_extra = {}
            if self._get_telemetry_callback:
                try:
                    telemetry_extra = self._get_telemetry_callback() or {}
                except Exception:
                    pass

            endpoint = f"{self.server_url}/api/v1/telemetry/heartbeat"
            payload = {
                "license_key": self.license_key,
                "hwid": self.hwid,
                "hostname": platform.node(),
                "os_version": f"{platform.system()} {platform.release()}",
                "bot_token_prefix": telemetry_extra.get("bot_token_prefix", ""),
                "telegram_chat_id": telemetry_extra.get("telegram_chat_id", ""),
                "active_strategies": telemetry_extra.get("active_strategies", []),
                "quotex_logged_in": telemetry_extra.get("quotex_logged_in", False),
                "scanner_active": telemetry_extra.get("scanner_active", False)
            }

            try:
                req_data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    endpoint,
                    data=req_data,
                    headers={"Content-Type": "application/json", "User-Agent": "TradePulse-Personal/2.0"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    pass
            except Exception as e:
                logger.debug(f"[HEARTBEAT] ping note: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {
            "hwid": self.hwid,
            "license_key": self.license_key,
            "server_url": self.server_url,
            "is_licensed": self.is_licensed,
            "customer_name": self.customer_name,
            "expires_at": self.expires_at,
            "last_error": self.last_error_message
        }


license_client = LicenseClient()
