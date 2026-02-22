"""
Windows Native Integration (Phase 12 - Task 36).

Provides native Windows capabilities including clipboard access and WSL detection.
"""

import os
import subprocess
import sys
from typing import Any, Dict


def wsl_detect() -> Dict[str, Any]:
    """
    Detect if running in WSL (Windows Subsystem for Linux).

    Returns:
        Dictionary with:
        - is_wsl: bool - True if running in WSL
        - version: int | None - WSL version (1 or 2) if detected
    """
    if sys.platform != "linux":
        return {"is_wsl": False, "version": None}

    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                content = f.read().lower()
                if "microsoft" in content:
                    # WSL2 has "wsl2" in the version string
                    version = 2 if "wsl2" in content else 1
                    return {"is_wsl": True, "version": version}
    except Exception:
        pass

    return {"is_wsl": False, "version": None}


def clip_copy(text: str) -> bool:
    """
    Copy text to Windows clipboard.

    Works on both native Windows and WSL by using clip.exe.

    Args:
        text: Text to copy to clipboard

    Returns:
        True if successful, False otherwise
    """
    try:
        if sys.platform == "win32":
            # Native Windows - use clip.exe
            subprocess.run(
                ["clip.exe"],
                input=text.encode("utf-16le"),
                check=True,
                capture_output=True
            )
            return True
        elif wsl_detect()["is_wsl"]:
            # WSL - use clip.exe from Windows
            subprocess.run(
                ["clip.exe"],
                input=text.encode("utf-16le"),
                check=True,
                capture_output=True
            )
            return True
        else:
            # Not Windows or WSL
            return False
    except Exception:
        return False


def get_windows_info() -> Dict[str, Any]:
    """
    Get Windows environment information.

    Returns:
        Dictionary with Windows-specific information
    """
    info = {
        "platform": sys.platform,
        "wsl": wsl_detect()
    }

    # Try to get Windows version if on Windows
    if sys.platform == "win32":
        try:
            import platform
            info["windows_version"] = platform.win32_ver()[0]
            info["windows_edition"] = platform.win32_edition()
        except Exception:
            pass

    return info
