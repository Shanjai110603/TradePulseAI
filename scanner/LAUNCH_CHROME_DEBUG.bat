@echo off
title Launch Chrome with Remote Debugging (Port 9222)
echo ============================================================
echo   Starting Google Chrome for TradePulse Live Scanner
echo   Runs with port 9222 enabled on your default profile
echo ============================================================
echo.

REM Close existing Chrome to release profile lock
echo Closing existing Chrome windows...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Launching Chrome on port 9222...
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 "https://qxbroker.com/en/trade"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 "https://qxbroker.com/en/trade"
) else (
    echo [ERROR] Chrome not found in standard directories!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Chrome is now running with debugging enabled on port 9222!
echo All your tabs and login cookies are active.
echo You can now click START in TradePulse Scanner!
echo ============================================================
echo.
timeout /t 5
