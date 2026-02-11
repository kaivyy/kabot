@echo off
REM Kabot Windows Startup Script
set KABOT_VENV=%USERPROFILE%\.kabotenv
set PYTHON_EXE=%KABOT_VENV%\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo Kabot not installed. Run: kabot onboard
    pause
    exit /b 1
)

start "Kabot" /MIN "%PYTHON_EXE%" -m kabot gateway
