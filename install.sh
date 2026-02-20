#!/usr/bin/env bash
set -euo pipefail

# Kabot Installation Script
# Usage: curl -fsSL https://github.com/kaivyy/kabot/main/install.sh | bash  

KABOT_VERSION="${KABOT_VERSION:-latest}"
INSTALL_DIR="${KABOT_INSTALL_DIR:-$HOME/.kabot}"
VENV_DIR="$INSTALL_DIR/venv"
BIN_DIR="${KABOT_BIN_DIR:-$HOME/.local/bin}"
MIN_PYTHON_VERSION="3.11"
IS_TERMUX=0
IS_WSL=0
IS_HEADLESS=0
IS_VPS=0
RUNTIME_OS="unknown"

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

detect_runtime() {
    local uname_out
    uname_out="$(uname -s 2>/dev/null || echo unknown)"
    case "$uname_out" in
        Linux*) RUNTIME_OS="linux" ;;
        Darwin*) RUNTIME_OS="macos" ;;
        CYGWIN*|MINGW*|MSYS*) RUNTIME_OS="windows" ;;
        *) RUNTIME_OS="unknown" ;;
    esac

    if [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"com.termux"* ]]; then
        IS_TERMUX=1
        RUNTIME_OS="termux"
        if [ -z "${KABOT_BIN_DIR:-}" ] && [ -n "${PREFIX:-}" ]; then
            BIN_DIR="$PREFIX/bin"
        fi
    fi

    if [ "$RUNTIME_OS" = "linux" ] && grep -qi "microsoft" /proc/version 2>/dev/null; then
        IS_WSL=1
    fi

    if [ -n "${SSH_CLIENT:-}" ] || [ -n "${SSH_TTY:-}" ] || [ -n "${CI:-}" ] || [ -f "/.dockerenv" ]; then
        IS_VPS=1
    fi

    if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
        IS_HEADLESS=1
    fi

    if [ "$IS_TERMUX" -eq 1 ]; then
        IS_HEADLESS=1
    fi
}

log_runtime_summary() {
    local tags=()
    [ "$IS_TERMUX" -eq 1 ] && tags+=("termux")
    [ "$IS_WSL" -eq 1 ] && tags+=("wsl")
    [ "$IS_VPS" -eq 1 ] && tags+=("vps")
    [ "$IS_HEADLESS" -eq 1 ] && tags+=("headless")

    if [ "${#tags[@]}" -gt 0 ]; then
        log_info "Detected environment: $RUNTIME_OS (${tags[*]})"
    else
        log_info "Detected environment: $RUNTIME_OS"
    fi
}

check_termux_prereqs() {
    if [ "$IS_TERMUX" -ne 1 ]; then
        return 0
    fi

    local missing=()
    for dep in pkg git rust clang cmake; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            missing+=("$dep")
        fi
    done

    if [ "${#missing[@]}" -gt 0 ]; then
        log_warn "Termux prerequisites missing: ${missing[*]}"
        log_warn "Install with: pkg update && pkg upgrade && pkg install python git rust binutils build-essential cmake clang"
    fi
}

is_interactive() {
    [ -t 0 ] && [ -t 1 ]
}

main() {
    # Print Logo
    echo -e "${GREEN}"
    cat << "EOF"
 ██╗  ██╗ █████╗ ██████╗  ██████╗ ████████╗
 ██║ ██╔╝██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝
 █████╔╝ ███████║██████╔╝██║   ██║   ██║   
 ██╔═██╗ ██╔══██║██╔══██╗██║   ██║   ██║   
 ██║  ██╗██║  ██║██████╔╝╚██████╔╝   ██║   
 ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝    ╚═╝   
EOF
    echo -e "${NC}"
    log_info "Installing Kabot AI Agent..."
    detect_runtime
    log_runtime_summary
    check_termux_prereqs

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
    cat > "$BIN_DIR/kabot" << WRAPPER
#!/usr/bin/env bash
VENV_DIR="$VENV_DIR"
exec "$VENV_DIR/bin/python" -m kabot "\$@"
WRAPPER
    chmod +x "$BIN_DIR/kabot"

    # Run doctor and setup
    log_info "Running system health check (doctor)..."
    "$VENV_DIR/bin/python" -m kabot doctor --fix

    if is_interactive; then
        log_info "Launching interactive setup wizard..."
        "$VENV_DIR/bin/python" -m kabot setup
    else
        log_warn "Non-interactive shell detected. Skipping setup wizard."
        log_info "Run this after install: $BIN_DIR/kabot setup"
    fi

    echo ""
    log_info "Installation complete!"
    log_info "Kabot binary: $BIN_DIR/kabot"
    echo ""
    if is_interactive; then
        read -r -p "Press Enter to exit..."
    fi
}

main "$@"
