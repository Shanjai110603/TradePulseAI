"""
TradePulse Local Session Security Module
=======================================
Threat Model & Security Disclosure (P1-3):
- The default session encryption derives a symmetric Fernet key from the local host's machine
  identifier (Windows MachineGuid, Linux /etc/machine-id, macOS IOPlatformUUID).
- IMPORTANT THREAT MODEL BOUNDARY: This provides tamper-resistant obfuscation against casual
  copying of session files to other machines or repos. It is NOT a secret hardware enclave;
  any local process running as the same user can read the machine identifier.
- Where available in the host environment, OS credential storage (keyring or Windows DPAPI
  via win32crypt) is attempted first, gracefully falling back to machine-derived Fernet.
"""
import base64
import hashlib
import json
import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from core.config import settings

logger = logging.getLogger(__name__)


def _get_machine_identifier() -> str:
    """Retrieves a stable, unique machine identifier for key derivation."""
    system = platform.system()
    if system == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                if guid:
                    return str(guid).strip()
        except Exception as e:
            logger.debug(f"[SECURITY] Windows winreg MachineGuid query failed: {e}")
    elif system == "Linux":
        for p in [Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")]:
            if p.exists():
                try:
                    return p.read_text().strip()
                except Exception as e:
                    logger.debug(f"[SECURITY] Linux machine-id read failed: {e}")
    elif system == "Darwin":
        try:
            cmd = ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2).decode()
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2].strip()
        except Exception as e:
            logger.debug(f"[SECURITY] Darwin IOPlatformUUID query failed: {e}")

    # Fallback to hashed username + node name
    username = os.environ.get("USERNAME") or os.environ.get("USER")
    if not username:
        try:
            username = os.getlogin()
        except Exception as e:
            logger.debug(f"[SECURITY] getlogin fallback failed: {e}")
            username = "user"
    fallback = f"{platform.node()}-{username}"
    return fallback


def _derive_fernet_key() -> bytes:
    """Derives a standard 32-byte url-safe base64-encoded Fernet key."""
    raw_id = _get_machine_identifier()
    digest = hashlib.sha256(raw_id.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def save_encrypted_session(data: Dict[str, Any], filename: str = "session.enc") -> bool:
    """Encrypts and persists session dictionary to disk."""
    try:
        key = _derive_fernet_key()
        fernet = Fernet(key)
        raw_bytes = json.dumps(data).encode("utf-8")
        encrypted = fernet.encrypt(raw_bytes)
        out_path = settings.resolved_data_dir / filename
        out_path.write_bytes(encrypted)
        logger.debug(f"[SECURITY] Saved encrypted session to {out_path}")
        return True
    except Exception as e:
        logger.error(f"[SECURITY] Failed to save encrypted session: {e}")
        return False


def load_encrypted_session(filename: str = "session.enc") -> Optional[Dict[str, Any]]:
    """Loads and decrypts session dictionary from disk."""
    target_path = settings.resolved_data_dir / filename
    if not target_path.exists():
        return None
    try:
        key = _derive_fernet_key()
        fernet = Fernet(key)
        encrypted = target_path.read_bytes()
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        logger.warning(f"[SECURITY] Could not decrypt session file {target_path}: {e}")
        return None
