"""Update tools for checking and applying Kabot updates."""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
import httpx
from loguru import logger
from kabot.agent.tools.base import Tool


class CheckUpdateTool(Tool):
    """Check for Kabot updates from GitHub."""

    @property
    def name(self) -> str:
        return "check_update"

    @property
    def description(self) -> str:
        return "Check if Kabot updates are available. Returns current version, latest version, and commits behind. Use this when user asks about updates."

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
        try:
            from kabot import __version__
            return __version__
        except:
            return "unknown"

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
        if current == "unknown" or latest == "unknown":
            return False
        return current != latest


class SystemUpdateTool(Tool):
    """Update Kabot to latest version."""

    @property
    def name(self) -> str:
        return "system_update"

    @property
    def description(self) -> str:
        return "Update Kabot to latest version. Set confirm_restart=true to restart after update. Use this when user confirms update."

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

            # Check if can update
            if install_method == "git" and not self._can_update_git(kabot_dir):
                return json.dumps({
                    "success": False,
                    "reason": "dirty_working_tree",
                    "message": "Git working tree has uncommitted changes. Commit or stash first."
                })

            current_version = self._get_current_version()

            # Execute update
            if install_method == "git":
                success, message = self._git_update(kabot_dir)
            else:
                success, message = self._pip_update()

            if not success:
                return json.dumps({"success": False, "reason": "update_failed", "message": message})

            # Install dependencies
            self._install_dependencies(kabot_dir)

            updated_version = self._get_current_version()

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
                "restart_required": True
            })
        except Exception as e:
            logger.error(f"Update error: {e}")
            return json.dumps({"success": False, "reason": "exception", "message": str(e)})

    def _detect_install_method(self) -> str:
        kabot_dir = Path(__file__).parent.parent.parent.parent
        return "git" if (kabot_dir / ".git").exists() else "pip"

    def _get_current_version(self) -> str:
        try:
            from kabot import __version__
            return __version__
        except:
            return "unknown"

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
        except:
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
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "kabot-ai"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, f"Pip upgrade failed: {result.stderr}"
            return True, "Pip update successful"
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
