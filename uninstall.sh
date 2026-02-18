#!/bin/bash
# Kabot Uninstaller for Linux/Mac

KEEP_CONFIG=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-config) KEEP_CONFIG=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

SERVICE_NAME="kabot"
INSTALL_PATH="$HOME/.kabot"
BIN_PATH="$HOME/.local/bin/kabot"

if [ "$DRY_RUN" = true ]; then
    echo "DRY RUN - Would perform these actions:"
fi

# Remove systemd service
if systemctl --user is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
    if [ "$DRY_RUN" = true ]; then
        echo "- Stop and disable service: $SERVICE_NAME"
    else
        systemctl --user stop "$SERVICE_NAME"
        systemctl --user disable "$SERVICE_NAME"
        sudo rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        sudo systemctl daemon-reload
        echo "Service removed"
    fi
fi

# Remove binary symlink
if [ -L "$BIN_PATH" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo "- Remove binary: $BIN_PATH"
    else
        rm "$BIN_PATH"
        echo "Binary removed"
    fi
fi

# Remove installation directory
if [ -d "$INSTALL_PATH" ]; then
    if [ "$KEEP_CONFIG" = false ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "- Remove directory: $INSTALL_PATH"
        else
            rm -rf "$INSTALL_PATH"
            echo "Installation directory removed"
        fi
    else
        echo "Keeping configuration as requested"
    fi
fi

if [ "$DRY_RUN" = false ]; then
    echo "Kabot uninstalled successfully"
fi