@echo off
setlocal EnableExtensions
title Kabot Watchdog
echo Starting Kabot Watchdog...

cd /d "%~dp0"

set "KABOT_PY=py"
where %KABOT_PY% >nul 2>nul
if not "%ERRORLEVEL%"=="0" set "KABOT_PY=python"
where %KABOT_PY% >nul 2>nul

if not "%ERRORLEVEL%"=="0" (
    echo ERROR: Python launcher not found in PATH.
    echo Install Python and ensure py or python is available.
    goto end
)

:loop
%KABOT_PY% -u -m kabot gateway
set "EC=%ERRORLEVEL%"
if "%EC%"=="0" goto normal_stop
if "%EC%"=="42" goto restart_loop
if "%EC%"=="78" goto port_busy

echo Kabot crashed. Restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop

:normal_stop
echo Kabot stopped normally.
goto end

:restart_loop
echo Restarting Kabot (user request)...
timeout /t 1 /nobreak >nul
goto loop

:port_busy
echo Gateway port already in use. Another Kabot instance may be running.
echo Exiting watchdog to avoid retry loop.
goto end

:end
pause
