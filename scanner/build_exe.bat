@echo off
title Build TradePulse Scanner App (.exe)
echo ============================================================
echo   Building TradePulse Quotex Scanner into Standalone .exe
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Please ensure Python is added to PATH.
    pause
    exit /b 1
)

echo [1/3] Ensuring required build tools...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install pyinstaller httpx websockets >nul 2>&1

echo.
echo [2/3] Building TradePulseScanner.exe via PyInstaller...
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "TradePulseScanner" ^
    --add-data "browser_agent.py;." ^
    --add-data "strategy_engine.py;." ^
    --add-data "telegram_bridge.py;." ^
    quotex_scanner.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check output above.
    pause
    exit /b 1
)

echo.
echo [3/3] Build Successful!
echo ============================================================
echo Your executable is ready at:
echo   %~dp0dist\TradePulseScanner.exe
echo ============================================================
echo.
pause
