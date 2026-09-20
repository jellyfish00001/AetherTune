@echo off
title AetherTune - VCClient Voice Changer
cd /d "%~dp0tools\external\VCClient\2.1.4-alpha\dist\main"

echo ========================================================
echo   Starting AetherTune Real-time Voice Changer...
echo   Web UI: http://127.0.0.1:18000/
echo ========================================================
echo.

start "" "http://127.0.0.1:18000/"
main.exe start --https false

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] VCClient exited with error code %ERRORLEVEL%
    pause
)
