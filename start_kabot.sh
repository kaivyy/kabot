#!/bin/bash

# Kabot Watchdog Script
echo "🦅 Starting Kabot Watchdog..."

while true; do
    python3 -m kabot gateway
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Kabot stopped normally."
        break
    elif [ $EXIT_CODE -eq 42 ]; then
        echo "🔄 Restarting Kabot (User Request)..."
        sleep 1
    else
        echo "⚠️ Kabot crashed with code $EXIT_CODE. Restarting in 5s..."
        sleep 5
    fi
done
