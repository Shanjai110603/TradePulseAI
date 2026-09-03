@echo off
title TradePulse Backend API
cd /d C:\TradePulse\backend
echo ========================================================
echo Starting TradePulse Backend API and Telegram Service...
echo ========================================================
uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo Backend process exited.
pause
