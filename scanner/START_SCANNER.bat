@echo off
title TradePulse Quotex Multi-Currency Scanner
echo ============================================================
echo   TradePulse Quotex Multi-Currency Scanner
echo   Streams 20+ OTC currencies to the TradePulse Bot
echo ============================================================
echo.

REM Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Install Python 3.10+ first.
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Checking dependencies...
pip install httpx websockets >nul 2>&1

REM Check if the bot backend is running
echo Checking bot backend at http://127.0.0.1:8000...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: Bot backend not detected at port 8000!
    echo Make sure uvicorn is running first:
    echo   cd C:\TradePulse\backend
    echo   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    echo.
    echo Press any key to continue anyway, or Ctrl+C to abort...
    pause >nul
)

echo.
echo Starting scanner... (Chrome will launch automatically)
echo Press Ctrl+C to stop.
echo.

python "%~dp0quotex_scanner.py"

echo.
echo Scanner stopped.
pause
