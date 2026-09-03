@echo off
title Launch Chrome with Remote Debugging (Port 9222)
echo ============================================================
echo   Starting Google Chrome for TradePulse Real Data Relay
echo   Runs on Port 9222 with your active Quotex profile
echo ============================================================
echo.

echo Closing existing Chrome windows...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Launching Chrome on port 9222 with dedicated debug profile...
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\TradePulse\chrome_debug_profile" "https://qxbroker.com/en/trade"
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\TradePulse\chrome_debug_profile" "https://qxbroker.com/en/trade"
) else (
    echo [ERROR] Chrome not found in standard directories!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Chrome is now running with Port 9222 enabled!
echo Quotex is open and your login session is ready.
echo Now start the relay in PowerShell!
echo ============================================================
echo.
timeout /t 4
