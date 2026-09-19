@echo off
REM ==============================================================================
REM TradePulse Windows Standalone Executable Packager
REM Compiles TradePulse into a single portable TradePulse.exe with PyInstaller
REM ==============================================================================

echo [*] Checking Python environment...
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH.
    pause
    exit /b 1
)

echo [*] Installing build dependencies...
pip install pyinstaller pywebview websockets httpx pydantic pydantic-settings cryptography pillow matplotlib

echo [*] Building TradePulse.exe with PyInstaller using TradePulse.spec...
pyinstaller --noconfirm --clean "..\TradePulse.spec"

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo [SUCCESS] TradePulse.exe successfully packaged!
    echo Output directory: dist\TradePulse\TradePulse.exe
    echo ========================================================
) else (
    echo [ERROR] Build failed. Check compiler log above.
)

pause
