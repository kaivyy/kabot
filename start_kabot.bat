@echo off
setlocal
title Kabot Watchdog
echo Starting Kabot Watchdog...

cd /d "%~dp0"

set "KABOT_PY="
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "KABOT_PY=py"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "KABOT_PY=python"
    )
)

if "%KABOT_PY%"=="" (
    echo ERROR: Python launcher not found in PATH.
    echo Install Python and ensure ^`py^` or ^`python^` is available.
    goto end
)

:loop
%KABOT_PY% -m kabot gateway
if %ERRORLEVEL% EQU 0 (
    echo Kabot stopped normally.
    goto end
)
if %ERRORLEVEL% EQU 42 (
    echo Restarting Kabot (user request)...
    timeout /t 1 /nobreak >nul
    goto loop
)

echo Kabot crashed. Restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop

:end
pause
