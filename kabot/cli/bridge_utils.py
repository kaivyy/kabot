"""Bridge utilities to avoid circular imports."""

from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich.console import Console

from kabot import __logo__

console = Console()


def _bridge_host_port(bridge_url: str) -> tuple[str, int]:
    parsed = urlparse(bridge_url)
    host = parsed.hostname or "localhost"
    if parsed.port:
        return host, parsed.port
    if parsed.scheme == "wss":
        return host, 443
    return host, 80


def is_local_bridge_url(bridge_url: str) -> bool:
    parsed = urlparse(bridge_url)
    return parsed.scheme in {"ws", "wss"} and (parsed.hostname or "").lower() in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def is_bridge_reachable(bridge_url: str = "ws://localhost:3001", timeout_seconds: float = 1.0) -> bool:
    host, port = _bridge_host_port(bridge_url)
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def wait_for_bridge_ready(
    bridge_url: str = "ws://localhost:3001",
    timeout_seconds: float = 20.0,
    poll_interval_seconds: float = 0.5,
) -> bool:
    deadline = time.monotonic() + max(timeout_seconds, 0)
    while time.monotonic() <= deadline:
        if is_bridge_reachable(bridge_url):
            return True
        time.sleep(max(poll_interval_seconds, 0.05))
    return False


def _bridge_env(bridge_url: str) -> dict[str, str]:
    """Environment for launching the bridge process on the configured port."""
    _host, port = _bridge_host_port(bridge_url)
    env = os.environ.copy()
    env["BRIDGE_PORT"] = str(port)
    return env


def _list_listening_pids_windows(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return []

    pids: set[int] = set()
    suffix = f":{port}"
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        proto, local_addr, _foreign_addr, state, pid_raw = parts[:5]
        if proto.upper() != "TCP":
            continue
        if state.upper() != "LISTENING":
            continue
        if not local_addr.endswith(suffix):
            continue
        try:
            pids.add(int(pid_raw))
        except ValueError:
            continue
    return sorted(pids)


def _list_listening_pids_unix(port: int) -> list[int]:
    pids: set[int] = set()
    lsof = shutil.which("lsof")
    if lsof:
        try:
            result = subprocess.run(
                [lsof, "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            for line in result.stdout.splitlines():
                value = line.strip()
                if not value:
                    continue
                try:
                    pids.add(int(value))
                except ValueError:
                    continue
            return sorted(pids)
        except OSError:
            pass

    ss = shutil.which("ss")
    if ss:
        try:
            result = subprocess.run(
                [ss, "-ltnp"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            pattern = re.compile(rf":{port}\b.*pid=(\d+)")
            for line in result.stdout.splitlines():
                match = pattern.search(line)
                if not match:
                    continue
                try:
                    pids.add(int(match.group(1)))
                except ValueError:
                    continue
        except OSError:
            pass

    return sorted(pids)


def _list_listening_pids(port: int) -> list[int]:
    if os.name == "nt":
        return _list_listening_pids_windows(port)
    return _list_listening_pids_unix(port)


def _get_process_cmdline(pid: int) -> str:
    if pid <= 0:
        return ""
    if os.name == "nt":
        try:
            powershell = shutil.which("powershell") or shutil.which("pwsh")
            if not powershell:
                return ""
            command = f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").CommandLine"
            result = subprocess.run(
                [powershell, "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            return (result.stdout or "").strip()
        except OSError:
            return ""

    proc_cmdline = Path("/proc") / str(pid) / "cmdline"
    if proc_cmdline.exists():
        try:
            raw = proc_cmdline.read_bytes()
            return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        except OSError:
            return ""
    return ""


def _looks_like_kabot_bridge_process(command_line: str) -> bool:
    if not command_line:
        return False
    lowered = command_line.lower()
    bridge_markers = [
        "kabot-whatsapp-bridge",
        ".kabot\\bridge",
        "/.kabot/bridge",
        "\\kabot\\bridge\\dist\\index.js",
        "/kabot/bridge/dist/index.js",
        "bridge\\dist\\index.js",
        "bridge/dist/index.js",
    ]
    runtime_markers = ["node", "npm", "pnpm", "yarn", "bun"]
    return any(marker in lowered for marker in bridge_markers) and any(
        marker in lowered for marker in runtime_markers
    )


def _terminate_pid(pid: int) -> bool:
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            return result.returncode == 0
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def stop_bridge_processes(bridge_url: str = "ws://localhost:3001", require_signature: bool = True) -> list[int]:
    """Stop local bridge processes listening on the configured port."""
    if not is_local_bridge_url(bridge_url):
        return []
    _host, port = _bridge_host_port(bridge_url)
    killed: list[int] = []
    for pid in _list_listening_pids(port):
        if pid == os.getpid():
            continue
        cmdline = _get_process_cmdline(pid)
        if require_signature and not _looks_like_kabot_bridge_process(cmdline):
            continue
        if _terminate_pid(pid):
            killed.append(pid)
    return killed


def get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    # User's bridge location
    user_bridge = Path.home() / ".kabot" / "bridge"

    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge

    # Check for npm
    npm_path = shutil.which("npm")
    if not npm_path:
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)

    # Find source bridge: first check package data, then source dir
    # This assumes bridge_utils.py is in kabot/cli/
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # kabot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)

    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge

    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall kabot")
        raise typer.Exit(1)

    console.print(f"{__logo__} Setting up bridge...")

    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))

    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run([npm_path, "install"], cwd=user_bridge, check=True, capture_output=True)

        console.print("  Building...")
        subprocess.run([npm_path, "run", "build"], cwd=user_bridge, check=True, capture_output=True)

        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)

    return user_bridge


def start_bridge_background(bridge_url: str = "ws://localhost:3001", wait_seconds: float = 20.0) -> bool:
    """Start bridge as a background process when using local bridge URL."""
    if is_bridge_reachable(bridge_url):
        return True

    if not is_local_bridge_url(bridge_url):
        return False

    bridge_dir = get_bridge_dir()
    npm_path = shutil.which("npm")
    if not npm_path:
        console.print("[red]npm not found. Please install Node.js.[/red]")
        return False

    popen_kwargs: dict[str, object] = {
        "cwd": bridge_dir,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": _bridge_env(bridge_url),
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    try:
        subprocess.Popen([npm_path, "start"], **popen_kwargs)
    except Exception as exc:
        console.print(f"[red]Failed to start bridge background process: {exc}[/red]")
        return False

    return wait_for_bridge_ready(bridge_url=bridge_url, timeout_seconds=wait_seconds)


def run_bridge_login(
    stop_when_connected: bool = False,
    timeout_seconds: int = 180,
    *,
    bridge_url: str = "ws://localhost:3001",
    restart_if_running: bool = False,
) -> bool:
    """Link device via QR code.

    When ``stop_when_connected`` is True, this returns after successful pairing
    (or timeout) instead of blocking forever.
    """
    if is_local_bridge_url(bridge_url) and is_bridge_reachable(bridge_url):
        if restart_if_running:
            stopped = stop_bridge_processes(bridge_url=bridge_url)
            if stopped:
                time.sleep(0.8)
        if is_bridge_reachable(bridge_url):
            console.print(
                f"[yellow]Bridge already running at {bridge_url}. "
                "Use the existing terminal process or stop it first.[/yellow]"
            )
            return True

    bridge_dir = get_bridge_dir()

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")

    npm_path = shutil.which("npm")
    if not npm_path:
        console.print("[red]npm not found. Please install Node.js.[/red]")
        return False

    if not stop_when_connected:
        try:
            subprocess.run(
                [npm_path, "start"],
                cwd=bridge_dir,
                check=True,
                env=_bridge_env(bridge_url),
            )
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Bridge failed: {e}[/red]")
            return False

    process = subprocess.Popen(
        [npm_path, "start"],
        cwd=bridge_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=_bridge_env(bridge_url),
    )
    connected = False
    deadline = time.monotonic() + max(timeout_seconds, 1)

    try:
        while True:
            if process.stdout is None:
                break

            line = process.stdout.readline()
            if line:
                console.print(line.rstrip("\n"), markup=False, highlight=False)
                if "connected to whatsapp" in line.lower():
                    connected = True
                    break
            elif process.poll() is not None:
                break

            if time.monotonic() > deadline:
                console.print("[yellow]Bridge login timed out before connection confirmation.[/yellow]")
                break

        return connected
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
