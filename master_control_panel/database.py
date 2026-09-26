"""
Master Control Panel — Database & Persistence Layer
===================================================
Stores user licenses, 1-year subscriptions, single-device HWID bindings,
and real-time telemetry (active strategies, bot details, system specs).
"""
import sqlite3
import datetime
import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("TradePulse.MasterDB")

DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "master_database.db"


class MasterDatabase:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self._get_conn() as conn:
            # 1. Admin Credentials Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Licenses & Subscriptions Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS licenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT UNIQUE NOT NULL,
                    customer_name TEXT NOT NULL,
                    customer_email TEXT,
                    telegram_handle TEXT,
                    plan_name TEXT DEFAULT '1-Year Subscription',
                    status TEXT DEFAULT 'ACTIVE', -- ACTIVE, SUSPENDED, EXPIRED
                    max_devices INTEGER DEFAULT 1,
                    bound_hwids TEXT DEFAULT '[]', -- JSON array of authorized HWIDs
                    primary_hwid TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    notes TEXT DEFAULT ''
                )
            """)

            # 3. Client Telemetry & System Activity Table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS client_telemetry (
                    hwid TEXT PRIMARY KEY,
                    license_key TEXT NOT NULL,
                    hostname TEXT,
                    os_version TEXT,
                    ip_address TEXT,
                    bot_token_prefix TEXT,
                    telegram_chat_id TEXT,
                    active_strategies TEXT DEFAULT '[]', -- JSON array of strategy names
                    app_version TEXT DEFAULT '2.0 Personal',
                    quotex_logged_in BOOLEAN DEFAULT 0,
                    scanner_active BOOLEAN DEFAULT 0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (license_key) REFERENCES licenses (license_key) ON DELETE CASCADE
                )
            """)

            # Seed default admin if not exists (username: admin, password: adminPassword123!)
            cur = conn.cursor()
            cur.execute("SELECT id FROM admin_users WHERE username = 'admin'")
            if not cur.fetchone():
                default_pw_hash = hashlib.sha256("adminPassword123!".encode()).hexdigest()
                conn.execute(
                    "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                    ("admin", default_pw_hash)
                )
                logger.info("🔑 Initialized Master Admin Account (admin / adminPassword123!)")

    # -------------------------------------------------------------------------
    # License & Subscription Operations
    # -------------------------------------------------------------------------
    def create_license(
        self,
        customer_name: str,
        customer_email: str = "",
        telegram_handle: str = "",
        duration_days: int = 365,
        max_devices: int = 1,
        plan_name: str = "1-Year Subscription",
        notes: str = ""
    ) -> Dict[str, Any]:
        """Generates a secure 1-year subscription license key for a customer."""
        key_part = uuid.uuid4().hex[:16].upper()
        license_key = f"TP-PERS-{key_part[:4]}-{key_part[4:8]}-{key_part[8:12]}-{key_part[12:]}"
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(days=duration_days)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO licenses (
                    license_key, customer_name, customer_email, telegram_handle,
                    plan_name, status, max_devices, bound_hwids, primary_hwid,
                    created_at, expires_at, notes
                ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, '[]', '', ?, ?, ?)
            """, (
                license_key, customer_name, customer_email, telegram_handle,
                plan_name, max_devices, now.isoformat(), expires_at.isoformat(), notes
            ))

        return self.get_license(license_key)

    def get_license(self, license_key: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["bound_hwids"] = json.loads(res.get("bound_hwids") or "[]")
            return res

    def get_all_licenses(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT l.*, t.last_seen, t.os_version, t.hostname, t.bot_token_prefix, t.telegram_chat_id, t.active_strategies, t.scanner_active
                FROM licenses l
                LEFT JOIN client_telemetry t ON l.license_key = t.license_key
                ORDER BY l.created_at DESC
            """).fetchall()
            licenses = []
            for r in rows:
                d = dict(r)
                d["bound_hwids"] = json.loads(d.get("bound_hwids") or "[]")
                d["active_strategies"] = json.loads(d.get("active_strategies") or "[]")
                licenses.append(d)
            return licenses

    def validate_and_bind_license(
        self,
        license_key: str,
        hwid: str,
        system_info: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validates license and strictly enforces single-system binding.
        If system is new and quota allows, binds system. If bound to another system, rejects.
        """
        lic = self.get_license(license_key)
        if not lic:
            return False, "Invalid License Key. Please check your credentials.", None

        if lic.get("status") == "SUSPENDED":
            return False, "Subscription is Suspended by Master Administrator.", lic

        # Check expiration
        expires_at_str = lic.get("expires_at")
        try:
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            if now > expires_at:
                with self._get_conn() as conn:
                    conn.execute("UPDATE licenses SET status = 'EXPIRED' WHERE license_key = ?", (license_key,))
                return False, f"Subscription Expired on {expires_at.strftime('%Y-%m-%d')}. Please renew your plan.", lic
        except Exception as e:
            logger.error(f"Date check error: {e}")

        bound_hwids = lic.get("bound_hwids", [])
        max_devices = lic.get("max_devices", 1)

        # Single-System Enforcement Check
        if hwid in bound_hwids:
            # Already authorized on this machine
            pass
        elif len(bound_hwids) < max_devices:
            # New machine allowed within quota -> Bind it
            bound_hwids.append(hwid)
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE licenses 
                    SET bound_hwids = ?, primary_hwid = ?
                    WHERE license_key = ?
                """, (json.dumps(bound_hwids), hwid, license_key))
            lic["bound_hwids"] = bound_hwids
            logger.info(f"✅ Bound License {license_key} to HWID {hwid} (1/{max_devices} slots)")
        else:
            # Reached max systems! Cannot be used on this system without admin permission
            primary = lic.get("primary_hwid", "another machine")
            return False, (
                f"Unauthorized System Binding! This subscription is locked to 1 machine (ID: {primary[:8]}...). "
                "Multi-system usage or machine transfer requires Master Administrator permission."
            ), lic

        # Record / Update Telemetry
        self.record_telemetry(license_key=license_key, hwid=hwid, **system_info)
        return True, "License validated successfully. Single system verified.", lic

    def reset_hwid_binding(self, license_key: str) -> bool:
        """Un-binds machines so user can activate on a fresh computer."""
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE licenses 
                SET bound_hwids = '[]', primary_hwid = '' 
                WHERE license_key = ?
            """, (license_key,))
            conn.execute("DELETE FROM client_telemetry WHERE license_key = ?", (license_key,))
            return True

    def toggle_license_status(self, license_key: str, status: Optional[str] = None) -> str:
        lic = self.get_license(license_key)
        if not lic:
            return "NOT_FOUND"
        curr = lic.get("status", "ACTIVE")
        new_status = status or ("SUSPENDED" if curr == "ACTIVE" else "ACTIVE")
        with self._get_conn() as conn:
            conn.execute("UPDATE licenses SET status = ? WHERE license_key = ?", (new_status, license_key))
        return new_status

    def extend_license(self, license_key: str, additional_days: int = 365) -> Optional[str]:
        lic = self.get_license(license_key)
        if not lic:
            return None
        expires_at_str = lic.get("expires_at")
        try:
            exp = datetime.datetime.fromisoformat(expires_at_str)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            base_date = max(now, exp)
            new_exp = base_date + datetime.timedelta(days=additional_days)
            with self._get_conn() as conn:
                conn.execute("""
                    UPDATE licenses 
                    SET expires_at = ?, status = 'ACTIVE' 
                    WHERE license_key = ?
                """, (new_exp.isoformat(), license_key))
            return new_exp.isoformat()
        except Exception as e:
            logger.error(f"Error extending license: {e}")
            return None

    def set_max_devices(self, license_key: str, max_devices: int) -> bool:
        with self._get_conn() as conn:
            conn.execute("UPDATE licenses SET max_devices = ? WHERE license_key = ?", (max_devices, license_key))
            return True

    def delete_license(self, license_key: str) -> bool:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM client_telemetry WHERE license_key = ?", (license_key,))
            conn.execute("DELETE FROM licenses WHERE license_key = ?", (license_key,))
            return True

    # -------------------------------------------------------------------------
    # Telemetry Tracking Operations
    # -------------------------------------------------------------------------
    def record_telemetry(
        self,
        license_key: str,
        hwid: str,
        hostname: str = "",
        os_version: str = "",
        ip_address: str = "",
        bot_token_prefix: str = "",
        telegram_chat_id: str = "",
        active_strategies: Optional[List[str]] = None,
        app_version: str = "2.0 Personal",
        quotex_logged_in: bool = False,
        scanner_active: bool = False
    ):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        strat_json = json.dumps(active_strategies or [])
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO client_telemetry (
                    hwid, license_key, hostname, os_version, ip_address,
                    bot_token_prefix, telegram_chat_id, active_strategies,
                    app_version, quotex_logged_in, scanner_active, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hwid) DO UPDATE SET
                    license_key = excluded.license_key,
                    hostname = excluded.hostname,
                    os_version = excluded.os_version,
                    ip_address = excluded.ip_address,
                    bot_token_prefix = excluded.bot_token_prefix,
                    telegram_chat_id = excluded.telegram_chat_id,
                    active_strategies = excluded.active_strategies,
                    app_version = excluded.app_version,
                    quotex_logged_in = excluded.quotex_logged_in,
                    scanner_active = excluded.scanner_active,
                    last_seen = excluded.last_seen
            """, (
                hwid, license_key, hostname, os_version, ip_address,
                bot_token_prefix, telegram_chat_id, strat_json,
                app_version, int(quotex_logged_in), int(scanner_active), now
            ))

    def get_all_telemetry(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT t.*, l.customer_name, l.customer_email, l.status as license_status
                FROM client_telemetry t
                LEFT JOIN licenses l ON t.license_key = l.license_key
                ORDER BY t.last_seen DESC
            """).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["active_strategies"] = json.loads(d.get("active_strategies") or "[]")
                res.append(d)
            return res

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        with self._get_conn() as conn:
            total_licenses = conn.execute("SELECT COUNT(*) FROM licenses").fetchone()[0]
            active_licenses = conn.execute("SELECT COUNT(*) FROM licenses WHERE status = 'ACTIVE'").fetchone()[0]
            online_clients = conn.execute("""
                SELECT COUNT(*) FROM client_telemetry 
                WHERE datetime(last_seen) >= datetime('now', '-5 minutes')
            """).fetchone()[0]
            scanning_clients = conn.execute("""
                SELECT COUNT(*) FROM client_telemetry 
                WHERE scanner_active = 1 AND datetime(last_seen) >= datetime('now', '-5 minutes')
            """).fetchone()[0]

            return {
                "total_licenses": total_licenses,
                "active_licenses": active_licenses,
                "online_clients": online_clients,
                "scanning_clients": scanning_clients
            }

    # -------------------------------------------------------------------------
    # Admin Authentication
    # -------------------------------------------------------------------------
    def verify_admin(self, username: str, password: str) -> bool:
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM admin_users WHERE username = ? AND password_hash = ?",
                (username, pw_hash)
            ).fetchone()
            return bool(row)


master_db = MasterDatabase()
