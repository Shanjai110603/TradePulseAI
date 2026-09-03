@echo off
title TradePulse Quotex Browser Relay
cd /d C:\TradePulse\backend
echo ========================================================
echo Starting TradePulse Quotex Browser Relay (Headed)...
echo ========================================================
python -m app.relay.quotex_browser_relay --headed
echo.
echo Relay process exited.
pause
