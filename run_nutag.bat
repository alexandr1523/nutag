@echo off
:: This file runs the Nutag application through PowerShell
cd /d "%~dp0"
echo Launching Nutag...
powershell -NoProfile -ExecutionPolicy Bypass -File "run_app.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
