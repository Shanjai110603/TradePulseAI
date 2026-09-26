"""
TradePulse Master Control Panel — Business & Developer Web Server
=================================================================
Centralized licensing, single-system HWID enforcement, subscription management,
and real-time client telemetry tracking website for TradePulse Personal Edition.
"""
import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Include project root
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from master_control_panel.database import master_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [MasterPanel]: %(message)s"
)
logger = logging.getLogger("MasterControlPanel")

app = FastAPI(
    title="TradePulse Master Control Panel",
    description="Business & Developer Administration Suite for TradePulse Subscriptions",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# Pydantic Request Models
# -----------------------------------------------------------------------------
class AdminLoginRequest(BaseModel):
    username: str
    password: str

class CreateLicenseRequest(BaseModel):
    customer_name: str
    customer_email: Optional[str] = ""
    telegram_handle: Optional[str] = ""
    duration_days: Optional[int] = 365
    max_devices: Optional[int] = 1
    plan_name: Optional[str] = "1-Year Subscription"
    notes: Optional[str] = ""

class ValidateLicenseRequest(BaseModel):
    license_key: str
    hwid: str
    hostname: Optional[str] = ""
    os_version: Optional[str] = ""
    app_version: Optional[str] = "2.0 Personal"
    bot_token_prefix: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    active_strategies: Optional[List[str]] = []
    quotex_logged_in: Optional[bool] = False
    scanner_active: Optional[bool] = False

class ClientTelemetryHeartbeat(BaseModel):
    license_key: str
    hwid: str
    hostname: Optional[str] = ""
    os_version: Optional[str] = ""
    bot_token_prefix: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    active_strategies: Optional[List[str]] = []
    quotex_logged_in: Optional[bool] = False
    scanner_active: Optional[bool] = False

class ExtendLicenseRequest(BaseModel):
    days: Optional[int] = 365

class SetDevicesRequest(BaseModel):
    max_devices: int


# -----------------------------------------------------------------------------
# Client Licensing & Telemetry API (Called by Personal Desktop App)
# -----------------------------------------------------------------------------
@app.post("/api/v1/license/validate")
async def validate_license(req: ValidateLicenseRequest, request: Request):
    """
    Validates license key and enforces single-system machine binding (HWID).
    Called by TradePulse Personal client application on launch.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    system_info = {
        "hostname": req.hostname,
        "os_version": req.os_version,
        "ip_address": client_ip,
        "bot_token_prefix": req.bot_token_prefix,
        "telegram_chat_id": req.telegram_chat_id,
        "active_strategies": req.active_strategies,
        "app_version": req.app_version,
        "quotex_logged_in": req.quotex_logged_in,
        "scanner_active": req.scanner_active
    }

    valid, msg, lic_data = master_db.validate_and_bind_license(
        license_key=req.license_key.strip(),
        hwid=req.hwid.strip(),
        system_info=system_info
    )

    if not valid:
        return JSONResponse(status_code=403, content={
            "success": False,
            "message": msg,
            "license": lic_data
        })

    return {
        "success": True,
        "message": msg,
        "license": lic_data
    }


@app.post("/api/v1/telemetry/heartbeat")
async def client_heartbeat(req: ClientTelemetryHeartbeat, request: Request):
    """
    Periodic heartbeat from client app updating live bot status, active strategies, and system state.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    lic = master_db.get_license(req.license_key.strip())
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")

    # Verify that this heartbeat is from an authorized bound device
    bound_hwids = lic.get("bound_hwids", [])
    if req.hwid.strip() not in bound_hwids:
        raise HTTPException(status_code=403, detail="Unauthorized system")

    master_db.record_telemetry(
        license_key=req.license_key.strip(),
        hwid=req.hwid.strip(),
        hostname=req.hostname,
        os_version=req.os_version,
        ip_address=client_ip,
        bot_token_prefix=req.bot_token_prefix,
        telegram_chat_id=req.telegram_chat_id,
        active_strategies=req.active_strategies,
        quotex_logged_in=req.quotex_logged_in,
        scanner_active=req.scanner_active
    )
    return {"success": True, "status": "acknowledged"}


# -----------------------------------------------------------------------------
# Admin Master Control REST APIs (Developer / Business Dashboard)
# -----------------------------------------------------------------------------
@app.post("/api/v1/admin/login")
async def admin_login(req: AdminLoginRequest):
    valid = master_db.verify_admin(req.username, req.password)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid administrator credentials")
    return {"success": True, "token": "master_admin_session_active", "user": req.username}


@app.get("/api/v1/admin/stats")
async def get_admin_stats():
    return master_db.get_dashboard_metrics()


@app.get("/api/v1/admin/licenses")
async def get_all_licenses():
    return master_db.get_all_licenses()


@app.post("/api/v1/admin/licenses")
async def create_license(req: CreateLicenseRequest):
    lic = master_db.create_license(
        customer_name=req.customer_name,
        customer_email=req.customer_email or "",
        telegram_handle=req.telegram_handle or "",
        duration_days=req.duration_days or 365,
        max_devices=req.max_devices or 1,
        plan_name=req.plan_name or "1-Year Subscription",
        notes=req.notes or ""
    )
    return {"success": True, "license": lic}


@app.post("/api/v1/admin/licenses/{license_key}/reset-hwid")
async def reset_license_hwid(license_key: str):
    """Allows user to bind and activate on a new/transferred machine."""
    ok = master_db.reset_hwid_binding(license_key)
    return {"success": ok, "message": f"Hardware ID binding reset for {license_key}"}


@app.post("/api/v1/admin/licenses/{license_key}/toggle-status")
async def toggle_license_status(license_key: str):
    new_status = master_db.toggle_license_status(license_key)
    return {"success": True, "status": new_status}


@app.post("/api/v1/admin/licenses/{license_key}/extend")
async def extend_license(license_key: str, req: ExtendLicenseRequest):
    new_exp = master_db.extend_license(license_key, additional_days=req.days or 365)
    if not new_exp:
        raise HTTPException(status_code=404, detail="License not found")
    return {"success": True, "expires_at": new_exp}


@app.post("/api/v1/admin/licenses/{license_key}/set-max-devices")
async def set_max_devices(license_key: str, req: SetDevicesRequest):
    ok = master_db.set_max_devices(license_key, max_devices=req.max_devices)
    return {"success": ok, "max_devices": req.max_devices}


@app.delete("/api/v1/admin/licenses/{license_key}")
async def delete_license(license_key: str):
    ok = master_db.delete_license(license_key)
    return {"success": ok}


@app.get("/api/v1/admin/telemetry")
async def get_all_telemetry():
    return master_db.get_all_telemetry()


# Mount static assets for Master Admin Web Panel
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_admin_panel():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h2>TradePulse Master Control Panel Initializing...</h2>")


def start_server(host: str = "0.0.0.0", port: int = 8000):
    logger.info(f"🚀 Starting TradePulse Master Control Panel at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_server()
