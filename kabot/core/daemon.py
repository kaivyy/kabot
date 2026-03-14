"""
Multi-Platform Daemon Support (Phase 12 - Task 37).

Generates service files for auto-start on different platforms:
- systemd (Linux)
- launchd (macOS)
- Windows Task Scheduler (future)
"""

import os
import shutil
import subprocess
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
        python_path = sys.executable

    return f"""[Unit]
Description={description}
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
ExecStart={python_path} -m kabot gateway
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
        python_path = sys.executable

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
        <string>kabot</string>
        <string>gateway</string>
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

        commands = [
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", service_name],
            ["systemctl", "--user", "restart", service_name],
        ]
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
                return (
                    False,
                    (
                        f"Service file created at {unit_file}, but failed to apply systemd command: "
                        f"`{' '.join(command)}` ({detail}).\n"
                        f"Run manually:\n  systemctl --user daemon-reload\n"
                        f"  systemctl --user enable {service_name}\n"
                        f"  systemctl --user start {service_name}"
                    ),
                )
        return (
            True,
            (
                f"Service file created at {unit_file} and enabled/started.\n"
                f"Manage with:\n  systemctl --user status {service_name}\n"
                f"  systemctl --user restart {service_name}"
            ),
        )
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

    workdir_path = Path(workdir)
    logs_dir = workdir_path / "logs"

    # Generate plist file
    plist_content = generate_launchagent_plist(label, str(workdir_path))

    # User LaunchAgents directory
    launch_dir = Path.home() / "Library" / "LaunchAgents"
    launch_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    plist_file = launch_dir / f"{label}.plist"

    try:
        plist_file.write_text(plist_content)

        # Best effort unload old definition first (ignore exit code).
        subprocess.run(["launchctl", "unload", str(plist_file)], capture_output=True, text=True)
        load_result = subprocess.run(["launchctl", "load", "-w", str(plist_file)], capture_output=True, text=True)
        if load_result.returncode != 0:
            detail = load_result.stderr.strip() or load_result.stdout.strip() or "unknown error"
            return (
                False,
                (
                    f"Service file created at {plist_file}, but failed to load launchd service ({detail}).\n"
                    f"Run manually:\n  launchctl load -w {plist_file}\n"
                    f"  launchctl start {label}"
                ),
            )

        start_result = subprocess.run(["launchctl", "start", label], capture_output=True, text=True)
        if start_result.returncode != 0:
            detail = start_result.stderr.strip() or start_result.stdout.strip() or "unknown error"
            return (
                False,
                (
                    f"Service file created at {plist_file} and loaded, but failed to start ({detail}).\n"
                    f"Run manually:\n  launchctl start {label}"
                ),
            )

        return (
            True,
            (
                f"Service file created at {plist_file} and loaded/started.\n"
                f"Manage with:\n  launchctl list | grep {label}\n"
                f"  launchctl kickstart -k gui/$(id -u)/{label}"
            ),
        )
    except Exception as e:
        return False, f"Failed to create service file: {e}"


def install_windows_task_service(
    task_name: str = "kabot",
    workdir: Optional[str] = None,
    python_path: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Install Windows Task Scheduler task for kabot auto-start.

    Args:
        task_name: Task Scheduler task name
        workdir: Working directory for startup (defaults to current directory)
        python_path: Python executable path (defaults to current interpreter)

    Returns:
        Tuple of (success, message)
    """
    if sys.platform != "win32":
        return False, "Windows Task Scheduler is only available on Windows"

    workdir = workdir or os.getcwd()
    python_path = python_path or sys.executable
    task_command = f'"{python_path}" -m kabot gateway'

    create_cmd = [
        "schtasks",
        "/Create",
        "/TN",
        task_name,
        "/SC",
        "ONLOGON",
        "/RL",
        "LIMITED",
        "/TR",
        task_command,
        "/F",
    ]

    env = os.environ.copy()
    env["KABOT_WORKDIR"] = workdir
    result = subprocess.run(create_cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Unknown schtasks error"
        return False, f"Failed to create Windows task: {detail}"

    run_cmd = ["schtasks", "/Run", "/TN", task_name]
    run_result = subprocess.run(run_cmd, capture_output=True, text=True, env=env)
    if run_result.returncode == 0:
        return True, f"Windows startup task created and started: {task_name}"

    run_detail = run_result.stderr.strip() or run_result.stdout.strip() or "unknown run error"
    return (
        True,
        (
            f"Windows startup task created: {task_name}. "
            f"Immediate start failed ({run_detail}); task will run at next logon."
        ),
    )


def install_termux_service(
    service_name: str = "kabot",
    workdir: Optional[str] = None,
    python_path: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Install Termux service using termux-services (sv).

    Args:
        service_name: Name of the service
        workdir: Working directory (defaults to current directory)
        python_path: Python executable path (defaults to current interpreter)

    Returns:
        Tuple of (success, message)
    """
    from kabot.utils.environment import detect_runtime_environment
    runtime = detect_runtime_environment()
    if not runtime.is_termux:
        return False, "Termux services are only available on Termux"

    if not shutil.which("sv"):
        return False, "termux-services package is not installed. Please run: pkg install termux-services"

    workdir = workdir or os.getcwd()
    python_path = python_path or sys.executable
    prefix = os.getenv("PREFIX", "/data/data/com.termux/files/usr")
    service_dir = Path(prefix) / "var" / "service" / service_name

    try:
        service_dir.mkdir(parents=True, exist_ok=True)
        run_file = service_dir / "run"

        # Create the run script
        run_content = f"""#!/bin/sh
exec 2>&1
export KABOT_WORKDIR="{workdir}"
exec {python_path} -m kabot gateway
"""
        run_file.write_text(run_content)
        run_file.chmod(0o755)

        # Enable the service
        subprocess.run(["sv-enable", service_name], capture_output=True)
        up_result = subprocess.run(["sv", "up", service_name], capture_output=True, text=True)
        if up_result.returncode == 0:
            return True, f"Termux service installed, enabled, and started: {service_name}"

        up_detail = up_result.stderr.strip() or up_result.stdout.strip() or "unknown sv up error"
        return (
            True,
            (
                f"Termux service installed and enabled: {service_name}. "
                f"Immediate start failed ({up_detail}); run manually: sv up {service_name}"
            ),
        )
    except Exception as e:
        return False, f"Failed to create Termux service: {e}"


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
        status["service_available"] = True
        status["service_type"] = "task_scheduler"
        # Check if task exists
        result = subprocess.run(["schtasks", "/Query", "/TN", "kabot"], capture_output=True, text=True)
        if result.returncode == 0:
            status["installed"] = True

    elif "termux" in sys.platform or os.getenv("PREFIX"):
        status["service_available"] = True
        status["service_type"] = "termux"
        prefix = os.getenv("PREFIX", "/data/data/com.termux/files/usr")
        if (Path(prefix) / "var" / "service" / "kabot").exists():
            status["installed"] = True

    return status
