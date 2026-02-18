#!/bin/bash
# Linux Service Installer for Kabot

set -e

SERVICE_NAME="kabot"
SERVICE_USER="${SUDO_USER:-$USER}"
KABOT_HOME="$HOME/.kabot"
KABOT_BIN="$KABOT_HOME/venv/bin/kabot"

# Check if kabot is installed
if [ ! -f "$KABOT_BIN" ]; then
    echo "Error: Kabot not found at $KABOT_BIN"
    exit 1
fi

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Kabot AI Assistant Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$KABOT_HOME
ExecStart=$KABOT_BIN daemon
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "Service '$SERVICE_NAME' installed and started successfully"
echo "Status: $(sudo systemctl is-active $SERVICE_NAME)"