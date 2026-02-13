#!/usr/bin/env bash
set -euo pipefail

# Kabot Installation Script
# Usage: curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/kabot/master/install.sh | bash

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
  _  __     _           _
 | |/ /    | |         | |
 | ' / __ _| |__   ___ | |_
 |  < / _` | '_ \ / _ \| __|
 | . \ (_| | |_) | (_) | |_
 |_|\_\__,_|_.__/ \___/ \__|

EOF
    echo -e "${NC}"
    log_info "Installing Kabot AI Agent..."

    # Check for Python
    log_info "Checking for Python >= $MIN_PYTHON_VERSION..."
    if ! PYTHON_CMD=$(find_python); then
        log_error "Python $MIN_PYTHON_VERSION or higher is required but not found."
        log_error "Please install Python from https://www.python.org/downloads/"
        exit 1
    fi
    
    PYTHON_VERSION=$("$PYTHON_CMD" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    log_info "Found Python $PYTHON_VERSION at $(command -v "$PYTHON_CMD")"

    # Create installation directory
    log_info "Creating installation directory at $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$BIN_DIR"

    # Create virtual environment
    log_info "Creating virtual environment..."
    if [ -d "$VENV_DIR" ]; then
        log_warn "Virtual environment already exists. Removing old installation..."
        rm -rf "$VENV_DIR"
    fi
    "$PYTHON_CMD" -m venv "$VENV_DIR"

    # Activate virtual environment
    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel > /dev/null 2>&1

    # Install Kabot
    log_info "Installing kabot-ai package..."
    if [ "$KABOT_VERSION" = "latest" ]; then
        pip install kabot-ai
    else
        pip install "kabot-ai==$KABOT_VERSION"
    fi

    # Create wrapper script
    log_info "Creating kabot command wrapper..."
    cat > "$BIN_DIR/kabot" << 'WRAPPER'
#!/usr/bin/env bash
VENV_DIR="$HOME/.kabot/venv"
exec "$VENV_DIR/bin/python" -m kabot "$@"
WRAPPER
    chmod +x "$BIN_DIR/kabot"

    # Add to PATH if not already there
    SHELL_RC=""
    if [ -n "${BASH_VERSION:-}" ]; then
        SHELL_RC="$HOME/.bashrc"
    elif [ -n "${ZSH_VERSION:-}" ]; then
        SHELL_RC="$HOME/.zshrc"
    fi

    if [ -n "$SHELL_RC" ] && [ -f "$SHELL_RC" ]; then
        if ! grep -q "export PATH=\"\$HOME/.local/bin:\$PATH\"" "$SHELL_RC"; then
            log_info "Adding $BIN_DIR to PATH in $SHELL_RC..."
            echo '' >> "$SHELL_RC"
            echo '# Added by Kabot installer' >> "$SHELL_RC"
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
            log_warn "Please run: source $SHELL_RC"
        fi
    fi

    # Run onboarding
    log_info "Running onboarding..."
    "$VENV_DIR/bin/python" -m kabot onboard

    echo ""
    log_info "Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Login to a provider: kabot auth login [openai|anthropic|google|kimi|minimax]"
    echo "  2. See all methods: kabot auth methods <provider>"
    echo "  3. Check auth status: kabot auth status"
    echo "  4. Start the gateway: kabot gateway"
    echo "  5. Or chat directly: kabot agent -m 'Hello!'"
    echo ""
    echo "Documentation: https://github.com/YOUR_ORG/kabot"
    echo ""
    echo "To use kabot immediately in this session, run:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
}

main "$@"
