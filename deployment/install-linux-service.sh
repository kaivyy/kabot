#!/bin/bash
# Linux Service Installer for Kabot
# Installs Kabot as a systemd service with proper security and error handling

set -e

# Service configuration
SERVICE_NAME="kabot"
SERVICE_USER="${SUDO_USER:-$USER}"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# Cleanup function for error handling
cleanup() {
    if [ -f "$SERVICE_FILE" ]; then
        echo "Cleaning up: Removing service file due to installation failure"
        sudo rm -f "$SERVICE_FILE"
        sudo systemctl daemon-reload 2>/dev/null || true
    fi
}

# Set trap for cleanup on error
trap cleanup ERR

# Validate that the service user exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Error: User '$SERVICE_USER' does not exist"
    echo "Please ensure the user exists before installing the service"
    exit 1
fi

# Get absolute paths that resolve correctly for the target user
# This prevents the security flaw where $HOME expands to root's home when run with sudo
KABOT_HOME_ABS="$(eval echo ~"$SERVICE_USER")/.kabot"
KABOT_BIN_ABS="$KABOT_HOME_ABS/venv/bin/kabot"

# Validate that kabot is installed at the expected location
if [ ! -f "$KABOT_BIN_ABS" ]; then
    echo "Error: Kabot not found at $KABOT_BIN_ABS"
    echo "Please ensure Kabot is properly installed for user '$SERVICE_USER'"
    exit 1
fi

# Validate that the kabot binary is executable
if [ ! -x "$KABOT_BIN_ABS" ]; then
    echo "Error: Kabot binary at $KABOT_BIN_ABS is not executable"
    exit 1
fi

# Check if service already exists and handle idempotency
if systemctl is-enabled "$SERVICE_NAME" &>/dev/null; then
    echo "Service '$SERVICE_NAME' already exists. Updating configuration..."
    # Stop the service before updating
    if systemctl is-active "$SERVICE_NAME" &>/dev/null; then
        echo "Stopping existing service..."
        sudo systemctl stop "$SERVICE_NAME" || {
            echo "Warning: Failed to stop existing service"
        }
    fi
else
    echo "Installing new service '$SERVICE_NAME'..."
fi

# Create systemd service file with enhanced security and best practices
echo "Creating systemd service file at $SERVICE_FILE"
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Kabot AI Assistant Service
Documentation=https://github.com/your-org/kabot
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$KABOT_HOME_ABS
ExecStart=$KABOT_BIN_ABS daemon
Restart=always
RestartSec=10
TimeoutStopSec=30
KillMode=mixed

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$KABOT_HOME_ABS

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kabot

# Environment
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Environment=HOME=$KABOT_HOME_ABS

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd configuration
echo "Reloading systemd configuration..."
sudo systemctl daemon-reload || {
    echo "Error: Failed to reload systemd configuration"
    exit 1
}

# Enable the service
echo "Enabling service '$SERVICE_NAME'..."
sudo systemctl enable "$SERVICE_NAME" || {
    echo "Error: Failed to enable service '$SERVICE_NAME'"
    exit 1
}

# Start the service
echo "Starting service '$SERVICE_NAME'..."
sudo systemctl start "$SERVICE_NAME" || {
    echo "Error: Failed to start service '$SERVICE_NAME'"
    echo "Check service logs with: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
}

# Verify service is running
sleep 2
SERVICE_STATUS=$(sudo systemctl is-active "$SERVICE_NAME")
if [ "$SERVICE_STATUS" = "active" ]; then
    echo "✓ Service '$SERVICE_NAME' installed and started successfully"
    echo "Status: $SERVICE_STATUS"
    echo ""
    echo "Useful commands:"
    echo "  View logs: sudo journalctl -u $SERVICE_NAME -f"
    echo "  Stop service: sudo systemctl stop $SERVICE_NAME"
    echo "  Restart service: sudo systemctl restart $SERVICE_NAME"
    echo "  Disable service: sudo systemctl disable $SERVICE_NAME"
else
    echo "Warning: Service '$SERVICE_NAME' is not active (status: $SERVICE_STATUS)"
    echo "Check service logs with: sudo journalctl -u $SERVICE_NAME -f"
    exit 1
fi

# Clear the trap since we succeeded
trap - ERR