"""Update tools for checking and applying Kabot updates."""
import importlib.metadata as importlib_metadata
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from kabot.agent.tools.base import Tool


def _normalize_version(value: str | None) -> str:
    """Normalize version values like 'v0.5.9' -> '0.5.9'."""
    normalized = str(value or "").strip()
    if normalized.lower().startswith("v"):
        normalized = normalized[1:]
    return normalized


def _read_installed_version() -> str:
    """Read currently installed package version from distribution metadata."""
    for pkg_name in ("kabot", "kabot-ai"):
        try:
            version = importlib_metadata.version(pkg_name)
            normalized = str(version or "").strip()
            if normalized:
                return normalized
        except importlib_metadata.PackageNotFoundError:
            continue
        except Exception:
            continue
    try:
        from kabot import __version__
        return str(__version__)
    except Exception:
        return "unknown"


class CheckUpdateTool(Tool):
    """Check for Kabot updates from GitHub."""

    @property
    def name(self) -> str:
        return "check_update"

    @property
    def description(self) -> str:
        return """Check if Kabot updates are available from GitHub. Use when user asks about updates in ANY language.

WHEN TO USE:
- "periksa apakah ada update baru?" / "check for updates"
- "ada versi terbaru?" / "is there a new version?"
- "cek update kabot" / "check kabot update"

RETURNS: JSON with current_version, latest_version, update_available, commits_behind, install_method, release_url"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        try:
            install_method = self._detect_install_method()
            current_version = self._get_current_version()

            # Check GitHub API for latest release
            latest_release = await self._fetch_github_release()
            latest_version = latest_release.get("tag_name", "unknown")
            release_url = latest_release.get("html_url", "")

            # Check git status if git install
            commits_behind = 0
            if install_method == "git":
                commits_behind = self._check_commits_behind()

            update_available = self._compare_versions(current_version, latest_version)

            return json.dumps({
                "install_method": install_method,
                "current_version": current_version,
                "latest_version": latest_version,
                "commits_behind": commits_behind,
                "update_available": update_available,
                "release_url": release_url
            })
        except Exception as e:
            logger.error(f"Check update error: {e}")
            return json.dumps({"error": str(e), "update_available": False})

    def _detect_install_method(self) -> str:
        """Detect if installed via git or pip."""
        kabot_dir = Path(__file__).parent.parent.parent.parent
        if (kabot_dir / ".git").exists():
            return "git"
        return "pip"

    def _get_current_version(self) -> str:
        """Get current Kabot version."""
        return _read_installed_version()

    async def _fetch_github_release(self) -> dict:
        """Fetch latest release from GitHub API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://api.github.com/repos/kaivyy/kabot/releases/latest"
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.warning(f"GitHub API error: {e}")
        return {}

    def _check_commits_behind(self) -> int:
        """Check how many commits behind origin/main."""
        try:
            kabot_dir = Path(__file__).parent.parent.parent.parent
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..origin/main"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Git check error: {e}")
        return 0

    def _compare_versions(self, current: str, latest: str) -> bool:
        """Compare version strings."""
        current_norm = _normalize_version(current)
        latest_norm = _normalize_version(latest)
        if current_norm == "unknown" or latest_norm == "unknown":
            return False
        return current_norm != latest_norm


class SystemUpdateTool(Tool):
    """Update Kabot to latest version."""

    @property
    def name(self) -> str:
        return "system_update"

    @property
    def description(self) -> str:
        return """Update Kabot to latest version. Use when user confirms update in ANY language.

WHEN TO USE:
- "update program" / "update kabot"
- "install update" / "pasang update"
- "upgrade kabot" / "perbarui kabot"

PARAMETERS:
- confirm_restart: Set to true ONLY when user explicitly confirms restart

RETURNS: JSON with success, updated_from, updated_to, restart_required"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "confirm_restart": {
                    "type": "boolean",
                    "description": "Whether to restart Kabot after update"
                }
            },
            "required": []
        }

    async def execute(self, confirm_restart: bool = False, **kwargs: Any) -> str:
        try:
            install_method = self._detect_install_method()
            kabot_dir = Path(__file__).parent.parent.parent.parent
            latest_version, release_url = await self._fetch_latest_release()

            # Check if can update
            if install_method == "git" and not self._can_update_git(kabot_dir):
                return json.dumps({
                    "success": False,
                    "reason": "dirty_working_tree",
                    "message": "Git working tree has uncommitted changes. Commit or stash first.",
                    "notify_user": True,
                    "notify_message": "Update failed: working tree is dirty. Commit or stash first.",
                })

            current_version = self._get_current_version()

            # Execute update
            if install_method == "git":
                success, message = self._git_update(kabot_dir)
            else:
                success, message = self._pip_update()

            if not success:
                return json.dumps({
                    "success": False,
                    "reason": "update_failed",
                    "message": message,
                    "latest_version": latest_version,
                    "release_url": release_url,
                    "notify_user": True,
                    "notify_message": f"Update failed: {message}",
                })

            # Install dependencies
            self._install_dependencies(kabot_dir)

            updated_version = self._get_current_version()
            updated_norm = _normalize_version(updated_version)
            latest_norm = _normalize_version(latest_version)

            # For pip installs, enforce best-effort "latest release" guarantee when release data is available.
            if install_method == "pip" and latest_norm and latest_norm != "unknown" and updated_norm != latest_norm:
                mismatch_message = (
                    f"Update completed but installed version ({updated_version}) does not match latest release "
                    f"({latest_version}). Please retry or verify index mirror."
                )
                return json.dumps({
                    "success": False,
                    "reason": "not_latest_after_update",
                    "message": mismatch_message,
                    "updated_from": current_version,
                    "updated_to": updated_version,
                    "latest_version": latest_version,
                    "release_url": release_url,
                    "notify_user": True,
                    "notify_message": mismatch_message,
                    "restart_required": False,
                })

            # Handle restart
            if confirm_restart:
                from kabot.services.update_service import UpdateService
                service = UpdateService()
                script_path = service.create_restart_script()
                service.execute_restart(script_path)

            return json.dumps({
                "success": True,
                "updated_from": current_version,
                "updated_to": updated_version,
                "latest_version": latest_version,
                "release_url": release_url,
                "restart_required": True,
                "notify_user": True,
                "notify_message": (
                    f"Update completed on server: {current_version} -> {updated_version}. "
                    "Restart is required to fully apply the new runtime."
                ),
            })
        except Exception as e:
            logger.error(f"Update error: {e}")
            return json.dumps({
                "success": False,
                "reason": "exception",
                "message": str(e),
                "notify_user": True,
                "notify_message": f"Update failed: {e}",
            })

    def _detect_install_method(self) -> str:
        kabot_dir = Path(__file__).parent.parent.parent.parent
        return "git" if (kabot_dir / ".git").exists() else "pip"

    def _get_current_version(self) -> str:
        return _read_installed_version()

    async def _fetch_latest_release(self) -> tuple[str, str]:
        """Fetch latest release info for best-effort latest-version guarantee."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://api.github.com/repos/kaivyy/kabot/releases/latest"
                )
                if response.status_code == 200:
                    payload = response.json()
                    return (
                        str(payload.get("tag_name") or "unknown"),
                        str(payload.get("html_url") or ""),
                    )
        except Exception as e:
            logger.warning(f"GitHub latest-release check failed: {e}")
        return "unknown", ""

    def _can_update_git(self, kabot_dir: Path) -> bool:
        """Check if git working tree is clean."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and not result.stdout.strip()
        except Exception:
            return False

    def _git_update(self, kabot_dir: Path) -> tuple[bool, str]:
        """Update via git pull."""
        try:
            # Fetch
            result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return False, f"Git fetch failed: {result.stderr}"

            # Pull
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return False, f"Git pull failed: {result.stderr}"

            return True, "Git update successful"
        except Exception as e:
            return False, str(e)

    def _pip_update(self) -> tuple[bool, str]:
        """Update via pip."""
        try:
            # Preferred package name is "kabot"; fall back to legacy "kabot-ai" when needed.
            for package_name in ("kabot", "kabot-ai"):
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    return True, f"Pip update successful ({package_name})"
            return False, f"Pip upgrade failed: {result.stderr}"
        except Exception as e:
            return False, str(e)

    def _install_dependencies(self, kabot_dir: Path):
        """Install/update dependencies."""
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                cwd=kabot_dir,
                capture_output=True,
                timeout=120
            )
        except Exception as e:
            logger.warning(f"Dependency install warning: {e}")
