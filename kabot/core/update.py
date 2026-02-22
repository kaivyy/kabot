"""
Update and System Control services for Kabot.

Handles self-updating from git, dependency management, and process restart.
"""

import asyncio
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class UpdateService:
    """
    Self-updating mechanism for Kabot.

    Workflow:
        1. Git Pull (fetch latest changes)
        2. Dependency Check (compare requirements.txt hash)
        3. Install (pip install if deps changed)
        4. Report what changed
    """

    def __init__(self, workspace: Path | None = None):
        self._workspace = workspace or Path.cwd()

    async def check_for_updates(self) -> str:
        """Check if updates are available without applying them."""
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["git", "fetch", "--dry-run"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check if we're behind
            status = await asyncio.to_thread(
                subprocess.run,
                ["git", "status", "-uno", "--porcelain"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Get current branch
            branch_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            branch = branch_result.stdout.strip() or "unknown"

            # Get latest commit
            log_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "log", "--oneline", "-1"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            latest_commit = log_result.stdout.strip() or "unknown"

            return (
                f"📦 *Update Check*\n"
                f"─────────────────────────\n"
                f"  Branch: `{branch}`\n"
                f"  Latest: `{latest_commit}`\n"
                f"  Status: {'Clean' if not status.stdout.strip() else 'Modified'}\n"
            )

        except FileNotFoundError:
            return "❌ Git is not installed or not in PATH."
        except subprocess.TimeoutExpired:
            return "❌ Git operation timed out."
        except Exception as e:
            return f"❌ Update check failed: {str(e)}"

    async def run_update(self) -> str:
        """Execute the full update workflow."""
        steps: list[str] = []

        # Step 1: Git Pull
        try:
            pull_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "pull", "--rebase", "origin", "main"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=60,
            )
            if pull_result.returncode == 0:
                output = pull_result.stdout.strip()
                if "Already up to date" in output:
                    steps.append("✅ Already up to date")
                else:
                    steps.append(f"✅ Pulled latest changes:\n```\n{output[:200]}\n```")
            else:
                steps.append(f"❌ Git pull failed: {pull_result.stderr.strip()[:100]}")
                return self._format_update_report(steps, success=False)
        except Exception as e:
            steps.append(f"❌ Git pull error: {str(e)}")
            return self._format_update_report(steps, success=False)

        # Step 2: Check if requirements changed
        try:
            diff_result = await asyncio.to_thread(
                subprocess.run,
                ["git", "diff", "HEAD~1", "--name-only"],
                cwd=str(self._workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            changed_files = diff_result.stdout.strip().split("\n")
            deps_changed = any(
                f in changed_files
                for f in ["requirements.txt", "pyproject.toml", "setup.py"]
            )
        except Exception:
            deps_changed = False

        # Step 3: Install dependencies if changed
        if deps_changed:
            try:
                req_path = self._workspace / "requirements.txt"
                if req_path.exists():
                    install_result = await asyncio.to_thread(
                        subprocess.run,
                        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                        cwd=str(self._workspace),
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if install_result.returncode == 0:
                        steps.append("✅ Dependencies updated")
                    else:
                        steps.append(f"⚠️ Pip install warning: {install_result.stderr.strip()[:80]}")
            except Exception as e:
                steps.append(f"⚠️ Dependency install failed: {str(e)[:50]}")
        else:
            steps.append("✅ Dependencies unchanged (skipped)")

        return self._format_update_report(steps, success=True)

    def _format_update_report(self, steps: list[str], success: bool) -> str:
        """Format update report."""
        header = "🔄 *Update Report*" if success else "🔄 *Update Report (Failed)*"
        body = "\n".join(f"  {s}" for s in steps)
        footer = "\n💡 Run `/restart` to apply changes." if success else ""
        return f"{header}\n─────────────────────────\n{body}{footer}"


class SystemControl:
    """
    Low-level system control for Kabot.

    Handles process restart and system-level operations.
    """

    RESTART_FLAG_FILE = ".restart_requested"

    def __init__(self, workspace: Path | None = None):
        self._workspace = workspace or Path.cwd()

    async def restart(self) -> str:
        """
        Schedule a process restart.

        Creates a restart flag file and initiates shutdown.
        The process supervisor (systemd/Docker/etc.) will restart the process.
        """
        flag_path = self._workspace / self.RESTART_FLAG_FILE
        try:
            flag_path.write_text("restart")
            logger.info("Restart flag created. Initiating shutdown...")

            # Give time for the response to be sent
            asyncio.get_event_loop().call_later(2.0, self._do_restart)

            return (
                "🔄 *Restarting Kabot...*\n"
                "The bot will be back online in a few seconds.\n"
                "If it doesn't restart automatically, run `kabot gateway` manually."
            )
        except Exception as e:
            return f"❌ Restart failed: {str(e)}"

    def _do_restart(self) -> None:
        """Perform the actual restart."""
        system = platform.system()

        if system == "Linux":
            # Try systemctl first, fallback to os.execv
            try:
                subprocess.run(
                    ["systemctl", "restart", "kabot"],
                    timeout=5,
                    capture_output=True,
                )
            except Exception:
                logger.info("Systemd restart failed, using os.execv")
                os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            # Windows / macOS: re-exec the process
            os.execv(sys.executable, [sys.executable] + sys.argv)

    def check_restart_flag(self) -> bool:
        """Check if a restart was requested (for startup notification)."""
        flag_path = self._workspace / self.RESTART_FLAG_FILE
        if flag_path.exists():
            flag_path.unlink(missing_ok=True)
            return True
        return False

    async def get_system_info(self) -> str:
        """Get detailed system information."""
        info = [
            "💻 *System Information*",
            "─────────────────────────",
            f"  OS: {platform.system()} {platform.release()}",
            f"  Machine: {platform.machine()}",
            f"  Python: {sys.version.split()[0]}",
            f"  Executable: {sys.executable}",
            f"  Working Dir: {os.getcwd()}",
            f"  PID: {os.getpid()}",
        ]
        return "\n".join(info)
