@echo off
title Kabot Watchdog
echo Starting Kabot Watchdog...

:loop
python -m kabot gateway
if %ERRORLEVEL% EQU 0 (
    echo ✅ Kabot stopped normally.
    goto end
)
if %ERRORLEVEL% EQU 42 (
    echo 🔄 Restarting Kabot (User Request)...
    timeout /t 1 /nobreak >nul
    goto loop
)

echo ⚠️ Kabot crashed. Restarting in 5s...
timeout /t 5 /nobreak
goto loop

:end
pause
