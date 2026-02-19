"""Runtime environment detection helpers."""

from __future__ import annotations

import os
import platform as py_platform
import sys
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RuntimeEnvironment:
    """Snapshot of the current runtime environment."""

    platform: str
    is_windows: bool
    is_macos: bool
    is_linux: bool
    is_wsl: bool
    is_termux: bool
    is_vps: bool
    is_headless: bool
    is_ci: bool
    has_display: bool


def _detect_wsl(env: Mapping[str, str], sys_platform: str, proc_version_text: str) -> bool:
    if sys_platform != "linux":
        return False
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP"):
        return True
    return "microsoft" in proc_version_text.lower()


def _detect_termux(env: Mapping[str, str], sys_platform: str) -> bool:
    if sys_platform != "linux":
        return False
    prefix = env.get("PREFIX", "")
    home = env.get("HOME", "")
    if env.get("TERMUX_VERSION"):
        return True
    if "com.termux" in prefix or "com.termux" in home:
        return True
    if env.get("ANDROID_ROOT") and "termux" in prefix:
        return True
    return False


def detect_runtime_environment(
    *,
    env: Mapping[str, str] | None = None,
    sys_platform: str | None = None,
    platform_system: str | None = None,
    proc_version_text: str | None = None,
    dockerenv_exists: bool | None = None,
) -> RuntimeEnvironment:
    """Detect runtime environment in a cross-platform way."""

    env_map = env if env is not None else os.environ
    sys_plat = sys_platform or sys.platform
    plat_system = (platform_system or py_platform.system()).lower()

    if proc_version_text is None:
        if sys_plat == "linux":
            try:
                with open("/proc/version", "r", encoding="utf-8", errors="ignore") as f:
                    proc_version_text = f.read()
            except OSError:
                proc_version_text = ""
        else:
            proc_version_text = ""

    if dockerenv_exists is None:
        dockerenv_exists = os.path.exists("/.dockerenv")

    is_windows = sys_plat == "win32" or plat_system.startswith("windows")
    is_macos = sys_plat == "darwin" or plat_system == "darwin"
    is_linux = sys_plat == "linux" or plat_system == "linux"
    is_wsl = _detect_wsl(env_map, sys_plat, proc_version_text)
    is_termux = _detect_termux(env_map, sys_plat)

    is_ci = bool(env_map.get("CI"))
    is_ssh = bool(env_map.get("SSH_CLIENT") or env_map.get("SSH_TTY"))
    has_display = bool(env_map.get("DISPLAY") or env_map.get("WAYLAND_DISPLAY"))

    is_vps = bool(is_ci or is_ssh or dockerenv_exists)
    # Termux behaves like a headless gateway runtime for browser callbacks.
    is_headless = bool(is_termux or is_vps or ((is_linux or is_macos) and not has_display))

    if is_windows:
        platform_name = "windows"
    elif is_macos:
        platform_name = "macos"
    elif is_linux:
        platform_name = "linux"
    else:
        platform_name = sys_plat

    return RuntimeEnvironment(
        platform=platform_name,
        is_windows=is_windows,
        is_macos=is_macos,
        is_linux=is_linux,
        is_wsl=is_wsl,
        is_termux=is_termux,
        is_vps=is_vps,
        is_headless=is_headless,
        is_ci=is_ci,
        has_display=has_display,
    )


def recommended_gateway_mode(runtime: RuntimeEnvironment) -> str:
    """Return default setup mode suggestion for current runtime."""
    if runtime.is_headless or runtime.is_vps:
        return "remote"
    return "local"
