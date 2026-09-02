@echo off
title TradePulse Quotex Scanner v2
echo ============================================================
echo   TradePulse Quotex Scanner v2.0
echo   Self-Contained - Direct to Telegram - Real Screenshots
echo   NO BACKEND NEEDED
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

REM Install deps
echo Installing dependencies...
pip install httpx websockets >nul 2>&1
echo Done.
echo.

echo Launching TradePulse Scanner...
start "" pythonw "%~dp0quotex_scanner.py" 2>nul || python "%~dp0quotex_scanner.py"
