@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM TradePulse Pro — Complete Windows Application & Installer Build Pipeline
REM Compiles binary executable with PyInstaller and packages it with Inno Setup
REM Produces: dist\installer\TradePulse-Setup-v2.0.0.exe
REM ==============================================================================

echo.
echo ==============================================================================
echo   ⚡ TradePulse Pro — Standalone Installer Build System
echo ==============================================================================
echo.

cd /d "%~dp0\.."

REM 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not found in PATH.
    pause
    exit /b 1
)

REM 2. Generate Icon Assets if not present
if not exist "assets\icon.ico" (
    echo [*] Generating icon assets...
    python assets\generate_icon.py
)

REM 3. Run PyInstaller Build
echo.
echo [*] Phase 1: Compiling application with PyInstaller...
python -m PyInstaller --noconfirm --clean TradePulse.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller compilation failed.
    pause
    exit /b 1
)

echo [OK] PyInstaller compilation finished: dist\TradePulse\TradePulse.exe

REM 4. Locate Inno Setup Compiler (ISCC.exe)
echo.
echo [*] Phase 2: Locating Inno Setup 6 Compiler...
set "ISCC_PATH="

if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
    for %%X in (ISCC.exe) do (set "ISCC_PATH=%%~$PATH:X")
)

if "!ISCC_PATH!"=="" (
    echo [ERROR] Inno Setup compiler (ISCC.exe) not found!
    echo Please ensure Inno Setup 6 is installed via:
    echo   winget install JRSoftware.InnoSetup
    pause
    exit /b 1
)

echo [OK] Found Inno Setup Compiler at: "!ISCC_PATH!"

REM 5. Compile Inno Setup Script
echo.
echo [*] Phase 3: Building standalone Windows Setup Installer...
"!ISCC_PATH!" "deploy\tradepulse_setup.iss"
if %errorlevel% neq 0 (
    echo [ERROR] Inno Setup compilation failed.
    pause
    exit /b 1
)

echo.
echo ==============================================================================
echo   [SUCCESS] TradePulse Windows Installer Created!
echo   Installer Path: dist\installer\TradePulse-Setup-v2.0.0.exe
echo ==============================================================================
echo.

pause
