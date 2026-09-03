@echo off
title TradePulse System Launcher
cd /d C:\TradePulse

echo ========================================================
echo Launching TradePulse Full Stack...
echo ========================================================

start "TradePulse Backend" cmd /k "cd /d C:\TradePulse\backend && uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 4 /nobreak > nul
start "TradePulse Relay" cmd /k "cd /d C:\TradePulse\backend && python -m app.relay.quotex_browser_relay --headed"

echo.
echo Both windows have been launched!
echo Keep both windows open to maintain live 24/7 scanning.
echo.
pause
