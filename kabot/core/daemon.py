"""
Multi-Platform Daemon Support (Phase 12 - Task 37).

Generates service files for auto-start on different platforms:
- systemd (Linux)
- launchd (macOS)
- Windows Task Scheduler (future)
"""

import os
import sys
from pathlib import Path
from typing import Optional


def generate_systemd_unit(
    user: str,
    workdir: str,
    python_path: Optional[str] = None,
    description: str = "Kabot AI Assistant Service"
) -> str:
    """
    Generate a systemd unit file for Linux.

    Args:
        user: Username to run the service as
        workdir: Working directory for the service
        python_path: Path to Python executable (defaults to venv/bin/python)
        description: Service description

    Returns:
        Systemd unit file content
    """
    if python_path is None:
        python_path = f"{workdir}/venv/bin/python"

    return f"""[Unit]
Description={description}
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
ExecStart={python_path} -m kabot.cli start
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
"""


def generate_launchagent_plist(
    label: str,
    workdir: str,
    python_path: Optional[str] = None,
    description: str = "Kabot AI Assistant"
) -> str:
    """
    Generate a launchd plist file for macOS.

    Args:
        label: Reverse DNS label (e.g., com.kabot.agent)
        workdir: Working directory for the service
        python_path: Path to Python executable (defaults to venv/bin/python)
        description: Service description

    Returns:
        launchd plist file content
    """
    if python_path is None:
        python_path = f"{workdir}/venv/bin/python"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>kabot.cli</string>
        <string>start</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{workdir}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>{workdir}/logs/kabot.log</string>

    <key>StandardErrorPath</key>
    <string>{workdir}/logs/kabot.error.log</string>

    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
"""


def install_systemd_service(
    service_name: str = "kabot",
    user: Optional[str] = None,
    workdir: Optional[str] = None
) -> tuple[bool, str]:
    """
    Install systemd service for current user.

    Args:
        service_name: Name of the service
        user: Username (defaults to current user)
        workdir: Working directory (defaults to current directory)

    Returns:
        Tuple of (success, message)
    """
    if sys.platform != "linux":
        return False, "systemd is only available on Linux"

    if user is None:
        user = os.getenv("USER", "kabot")

    if workdir is None:
        workdir = os.getcwd()

    # Generate unit file
    unit_content = generate_systemd_unit(user, workdir)

    # User systemd directory
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    systemd_dir.mkdir(parents=True, exist_ok=True)

    unit_file = systemd_dir / f"{service_name}.service"

    try:
        unit_file.write_text(unit_content)
        return True, f"Service file created at {unit_file}\n\nTo enable and start:\n  systemctl --user enable {service_name}\n  systemctl --user start {service_name}"
    except Exception as e:
        return False, f"Failed to create service file: {e}"


def install_launchd_service(
    label: str = "com.kabot.agent",
    workdir: Optional[str] = None
) -> tuple[bool, str]:
    """
    Install launchd service for current user.

    Args:
        label: Reverse DNS label
        workdir: Working directory (defaults to current directory)

    Returns:
        Tuple of (success, message)
    """
    if sys.platform != "darwin":
        return False, "launchd is only available on macOS"

    if workdir is None:
        workdir = os.getcwd()

    # Generate plist file
    plist_content = generate_launchagent_plist(label, workdir)

    # User LaunchAgents directory
    launch_dir = Path.home() / "Library" / "LaunchAgents"
    launch_dir.mkdir(parents=True, exist_ok=True)

    plist_file = launch_dir / f"{label}.plist"

    try:
        plist_file.write_text(plist_content)
        return True, f"Service file created at {plist_file}\n\nTo load and start:\n  launchctl load {plist_file}\n  launchctl start {label}"
    except Exception as e:
        return False, f"Failed to create service file: {e}"


def get_service_status() -> dict:
    """
    Get current service installation status.

    Returns:
        Dictionary with platform and service status
    """
    status = {
        "platform": sys.platform,
        "service_available": False,
        "service_type": None,
        "installed": False
    }

    if sys.platform == "linux":
        status["service_available"] = True
        status["service_type"] = "systemd"
        # Check if service file exists
        systemd_dir = Path.home() / ".config" / "systemd" / "user"
        if (systemd_dir / "kabot.service").exists():
            status["installed"] = True

    elif sys.platform == "darwin":
        status["service_available"] = True
        status["service_type"] = "launchd"
        # Check if plist exists
        launch_dir = Path.home() / "Library" / "LaunchAgents"
        if (launch_dir / "com.kabot.agent.plist").exists():
            status["installed"] = True

    elif sys.platform == "win32":
        status["service_available"] = False
        status["service_type"] = "task_scheduler"
        status["note"] = "Windows Task Scheduler support coming soon"

    return status
