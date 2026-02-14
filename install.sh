#!/usr/bin/env bash
set -euo pipefail

# Kabot Installation Script
# Usage: curl -fsSL https://github.com/kaivyy/kabot/main/install.sh | bash  

KABOT_VERSION="${KABOT_VERSION:-latest}"
INSTALL_DIR="${KABOT_INSTALL_DIR:-$HOME/.kabot}"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="$HOME/.local/bin"
MIN_PYTHON_VERSION="3.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}==>${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}==>${NC} $1"
}

log_error() {
    echo -e "${RED}==> ERROR:${NC} $1" >&2
}

version_compare() {
    local version=$1
    local minimum=$2
    printf '%s\n%s\n' "$minimum" "$version" | sort -V -C
}

find_python() {
    for cmd in python3.13 python3.12 python3.11 python3 python; do
        if command -v "$cmd" > /dev/null 2>&1; then
            local py_version=$("$cmd" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
            if version_compare "$py_version" "$MIN_PYTHON_VERSION"; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

main() {
    # Print Logo
    echo -e "${GREEN}"
    cat << "EOF"
    _  __    _    ____   ____  _______ 
   | |/ /   / \  | __ ) / __ \|__   __|
   | ' /   / _ \  |  _ \| |  | |  | |   
   |  <    / ___ \ | |_) | |__| |  | |   
   | . \  / /   \ \|____/ \____/   |_|   
   |_|\_\/_/     \_\                     
EOF
    echo -e "${NC}"
    log_info "Installing Kabot AI Agent..."

    # Check for Python
    if ! PYTHON_CMD=$(find_python); then
        log_error "Python $MIN_PYTHON_VERSION or higher is required."
        exit 1
    fi

    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"

    # Create virtual environment
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
    fi
    "$PYTHON_CMD" -m venv "$VENV_DIR"

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip setuptools wheel

    # Install Kabot from LOCAL source if available
    if [ -f "pyproject.toml" ]; then
        log_info "Installing from local source..."
        pip install -e .
    else
        log_info "Installing from PyPI..."
        pip install kabot-ai
    fi

    # Create wrapper script
    cat > "$BIN_DIR/kabot" << 'WRAPPER'
#!/usr/bin/env bash
VENV_DIR="$HOME/.kabot/venv"
exec "$VENV_DIR/bin/python" -m kabot "$@"
WRAPPER
    chmod +x "$BIN_DIR/kabot"

    # Run doctor and setup
    log_info "Running system health check (doctor)..."
    "$VENV_DIR/bin/python" -m kabot doctor --fix

    log_info "Launching interactive setup wizard..."
    "$VENV_DIR/bin/python" -m kabot setup

    echo ""
    log_info "Installation complete!"
    echo ""
    read -p "Press Enter to exit..."
}

main "$@"
