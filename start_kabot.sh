#!/bin/bash

# Kabot Watchdog Script
echo "🦅 Starting Kabot Watchdog..."

while true; do
    python3 -u -m kabot gateway
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Kabot stopped normally."
        break
    elif [ $EXIT_CODE -eq 42 ]; then
        echo "🔄 Restarting Kabot (User Request)..."
        sleep 1
    elif [ $EXIT_CODE -eq 78 ]; then
        echo "🟡 Gateway port already in use. Another Kabot instance may be running."
        echo "Stopping watchdog to avoid retry loop."
        break
    else
        echo "⚠️ Kabot crashed with code $EXIT_CODE. Restarting in 5s..."
        sleep 5
    fi
done
