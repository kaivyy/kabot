#!/bin/bash
# Kabot Uninstaller for Linux/Mac
# Safely removes Kabot installation with cross-platform support

set -e  # Exit on any error

# Configuration
SERVICE_NAME="kabot"
INSTALL_PATH="$HOME/.kabot"
BIN_PATH="$HOME/.local/bin/kabot"
KEEP_CONFIG=false
DRY_RUN=false
VERBOSE=false
FORCE=false

# Platform detection
detect_platform() {
    case "$(uname -s)" in
        Linux*) echo "linux" ;;
        Darwin*) echo "mac" ;;
        *)
            echo "Error: Unsupported platform '$(uname -s)'. This script supports Linux and macOS only." >&2
            exit 1
            ;;
    esac
}

# Logging functions
log_info() {
    echo "INFO: $1"
}

log_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo "VERBOSE: $1"
    fi
}

log_error() {
    echo "ERROR: $1" >&2
}

log_warning() {
    echo "WARNING: $1" >&2
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check sudo availability and permissions
check_sudo() {
    if ! command_exists sudo; then
        log_error "sudo command not found. Some operations may require elevated privileges."
        return 1
    fi

    # Test sudo without password prompt for system operations
    if ! sudo -n true 2>/dev/null; then
        log_verbose "sudo requires password authentication"
    fi

    return 0
}

# Safe file removal with confirmation
safe_remove() {
    local path="$1"
    local description="$2"

    if [ ! -e "$path" ]; then
        log_verbose "$description does not exist: $path"
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "- Remove $description: $path"
        return 0
    fi

    # Safety check - ensure we're not removing critical system paths
    case "$path" in
        /|/bin|/usr|/etc|/var|/home|/root)
            log_error "Refusing to remove critical system path: $path"
            return 1
            ;;
    esac

    if [ "$FORCE" = false ] && [ -d "$path" ]; then
        echo "About to remove directory: $path"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Skipped removal of $description"
            return 0
        fi
    fi

    if rm -rf "$path" 2>/dev/null; then
        log_info "$description removed: $path"
    else
        log_error "Failed to remove $description: $path"
        return 1
    fi
}

# Remove systemd service (Linux)
remove_systemd_service() {
    log_verbose "Checking for systemd service"

    if ! command_exists systemctl; then
        log_verbose "systemctl not found, skipping systemd service removal"
        return 0
    fi

    # Check for user service first (consistent approach)
    if systemctl --user is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
        if [ "$DRY_RUN" = true ]; then
            echo "- Stop and disable user service: $SERVICE_NAME"
            echo "- Remove user service file: $HOME/.config/systemd/user/$SERVICE_NAME.service"
        else
            log_info "Stopping and disabling user service: $SERVICE_NAME"
            systemctl --user stop "$SERVICE_NAME" 2>/dev/null || log_warning "Failed to stop user service"
            systemctl --user disable "$SERVICE_NAME" 2>/dev/null || log_warning "Failed to disable user service"

            # Remove user service file
            local user_service_file="$HOME/.config/systemd/user/$SERVICE_NAME.service"
            if [ -f "$user_service_file" ]; then
                rm -f "$user_service_file"
                log_info "User service file removed"
            fi

            systemctl --user daemon-reload 2>/dev/null || log_warning "Failed to reload user systemd daemon"
        fi
        return 0
    fi

    # Check for system service as fallback
    if systemctl is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
        if [ "$DRY_RUN" = true ]; then
            echo "- Stop and disable system service: $SERVICE_NAME"
            echo "- Remove system service file: /etc/systemd/system/$SERVICE_NAME.service"
        else
            log_info "Stopping and disabling system service: $SERVICE_NAME"
            if check_sudo; then
                sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || log_warning "Failed to stop system service"
                sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || log_warning "Failed to disable system service"

                # Remove system service file
                local system_service_file="/etc/systemd/system/$SERVICE_NAME.service"
                if [ -f "$system_service_file" ]; then
                    sudo rm -f "$system_service_file"
                    log_info "System service file removed"
                fi

                sudo systemctl daemon-reload 2>/dev/null || log_warning "Failed to reload system systemd daemon"
            else
                log_error "Cannot remove system service without sudo access"
                return 1
            fi
        fi
        return 0
    fi

    log_verbose "No systemd service found for $SERVICE_NAME"
}

# Remove launchd service (macOS)
remove_launchd_service() {
    log_verbose "Checking for launchd service"

    local plist_file="$HOME/Library/LaunchAgents/com.kabot.$SERVICE_NAME.plist"

    if [ -f "$plist_file" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "- Unload and remove launchd service: $plist_file"
        else
            log_info "Unloading launchd service"
            launchctl unload "$plist_file" 2>/dev/null || log_warning "Failed to unload launchd service"

            if rm -f "$plist_file"; then
                log_info "Launchd service file removed"
            else
                log_error "Failed to remove launchd service file"
                return 1
            fi
        fi
    else
        log_verbose "No launchd service found"
    fi
}

# Remove service based on platform
remove_service() {
    local platform="$1"

    case "$platform" in
        linux)
            remove_systemd_service
            ;;
        mac)
            remove_launchd_service
            ;;
        *)
            log_error "Unknown platform for service removal: $platform"
            return 1
            ;;
    esac
}

# Validate installation paths
validate_paths() {
    log_verbose "Validating installation paths"

    # Check if paths look reasonable
    if [[ "$INSTALL_PATH" != "$HOME"* ]]; then
        log_warning "Installation path is not in user home directory: $INSTALL_PATH"
    fi

    if [[ "$BIN_PATH" != "$HOME"* ]] && [[ "$BIN_PATH" != "/usr/local/bin"* ]]; then
        log_warning "Binary path is not in expected location: $BIN_PATH"
    fi
}

# Show help information
show_help() {
    cat << EOF
Kabot Uninstaller

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --keep-config    Keep configuration files and data
    --dry-run        Show what would be removed without actually removing
    --verbose        Enable verbose output
    --force          Skip confirmation prompts
    --help           Show this help message

EXAMPLES:
    $0                    # Standard uninstall
    $0 --dry-run          # Preview what would be removed
    $0 --keep-config      # Uninstall but keep configuration
    $0 --force --verbose  # Force uninstall with detailed output

DESCRIPTION:
    This script safely removes Kabot installation from Linux and macOS systems.
    It handles both systemd (Linux) and launchd (macOS) services, removes binaries,
    and optionally removes configuration files.

    The script includes safety checks to prevent accidental removal of system files
    and provides detailed feedback about the uninstall process.
EOF
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --keep-config)
                KEEP_CONFIG=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information."
                exit 1
                ;;
        esac
    done
}

# Main uninstall function
main() {
    parse_arguments "$@"

    local platform
    platform=$(detect_platform)

    log_info "Kabot Uninstaller for $platform"
    log_verbose "Platform: $platform"
    log_verbose "Service name: $SERVICE_NAME"
    log_verbose "Install path: $INSTALL_PATH"
    log_verbose "Binary path: $BIN_PATH"

    if [ "$DRY_RUN" = true ]; then
        echo
        echo "DRY RUN - Would perform these actions:"
    fi

    validate_paths

    # Remove service
    if ! remove_service "$platform"; then
        log_warning "Service removal failed, continuing with other components"
    fi

    # Remove binary symlink
    if [ -L "$BIN_PATH" ] || [ -f "$BIN_PATH" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "- Remove binary: $BIN_PATH"
        else
            if rm -f "$BIN_PATH" 2>/dev/null; then
                log_info "Binary removed: $BIN_PATH"
            else
                log_error "Failed to remove binary: $BIN_PATH"
            fi
        fi
    else
        log_verbose "Binary not found: $BIN_PATH"
    fi

    # Remove installation directory
    if [ -d "$INSTALL_PATH" ]; then
        if [ "$KEEP_CONFIG" = false ]; then
            safe_remove "$INSTALL_PATH" "installation directory"
        else
            log_info "Keeping configuration as requested: $INSTALL_PATH"
        fi
    else
        log_verbose "Installation directory not found: $INSTALL_PATH"
    fi

    # Final status
    if [ "$DRY_RUN" = false ]; then
        echo
        log_info "Kabot uninstall completed successfully"
        if [ "$KEEP_CONFIG" = true ]; then
            log_info "Configuration preserved in: $INSTALL_PATH"
        fi
    else
        echo
        echo "DRY RUN completed. Use without --dry-run to perform actual uninstall."
    fi
}

# Run main function with all arguments
main "$@"