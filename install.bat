@echo off
TITLE Kabot AI - Installer
SETLOCAL EnableDelayedExpansion

:: Check if install.ps1 exists
if not exist "%~dp0install.ps1" (
    echo [ERROR] install.ps1 not found in this directory.
    pause
    exit /b 1
)

echo Starting Kabot AI Installation Wizard...
echo.

:: Run the PowerShell script with Bypass policy
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Installation failed.
    pause
)

ENDLOCAL
