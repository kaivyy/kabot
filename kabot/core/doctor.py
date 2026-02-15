"""
Doctor Service for Kabot.

Automatically diagnoses and repairs system state, database schemas,
authentication, and configuration issues.
"""

import asyncio
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic check."""
    check_id: str
    name: str
    status: str       # "ok", "warning", "error"
    message: str
    fixable: bool = False
    fix_applied: bool = False


class DoctorService:
    """
    Runs diagnostic checks and auto-fixes on the Kabot system.

    Checks:
        - Database schema integrity
        - API key / auth token validity
        - Required environment variables
        - Configuration file health
        - Dependency versions
    """

    def __init__(self, workspace: Path | None = None, config: Any = None):
        self._workspace = workspace or Path.cwd()
        self._config = config
        self._results: list[DiagnosticResult] = []

    async def run_all(self, auto_fix: bool = False) -> str:
        """
        Run all diagnostic checks.
        
        Args:
            auto_fix: If True, attempt to fix any issues found.
        
        Returns:
            Formatted diagnostic report.
        """
        self._results = []

        # Run checks
        await self._check_python_version()
        await self._check_dependencies()
        await self._check_config_file()
        await self._check_env_vars()
        await self._check_auth_keys()
        await self._check_database()
        await self._check_workspace()

        # Auto-fix if requested
        if auto_fix:
            for result in self._results:
                if result.status == "error" and result.fixable:
                    await self._attempt_fix(result)

        return self._format_report()

    async def _check_python_version(self) -> None:
        """Verify Python version meets minimum requirements."""
        version = sys.version_info
        if version >= (3, 11):
            self._results.append(DiagnosticResult(
                check_id="python_version",
                name="Python Version",
                status="ok",
                message=f"Python {version.major}.{version.minor}.{version.micro}",
            ))
        elif version >= (3, 10):
            self._results.append(DiagnosticResult(
                check_id="python_version",
                name="Python Version",
                status="warning",
                message=f"Python {version.major}.{version.minor} (3.11+ recommended)",
            ))
        else:
            self._results.append(DiagnosticResult(
                check_id="python_version",
                name="Python Version",
                status="error",
                message=f"Python {version.major}.{version.minor} is too old (need 3.10+)",
            ))

    async def _check_dependencies(self) -> None:
        """Check if critical dependencies are installed."""
        critical_deps = [
            ("openai", "OpenAI SDK"),
            ("anthropic", "Anthropic SDK"),
            ("google.generativeai", "Google AI SDK"),
            ("loguru", "Loguru Logger"),
            ("typer", "Typer CLI"),
            ("rich", "Rich Console"),
        ]

        missing = []
        for module_name, display_name in critical_deps:
            try:
                __import__(module_name)
            except ImportError:
                missing.append(display_name)

        if missing:
            self._results.append(DiagnosticResult(
                check_id="dependencies",
                name="Dependencies",
                status="error",
                message=f"Missing: {', '.join(missing)}",
                fixable=True,
            ))
        else:
            self._results.append(DiagnosticResult(
                check_id="dependencies",
                name="Dependencies",
                status="ok",
                message=f"All {len(critical_deps)} critical packages installed",
            ))

    async def _check_config_file(self) -> None:
        """Verify config.json exists and is valid."""
        config_path = self._workspace / "config.json"
        if not config_path.exists():
            self._results.append(DiagnosticResult(
                check_id="config_file",
                name="Configuration",
                status="error",
                message="config.json not found",
                fixable=True,
            ))
            return

        try:
            import json
            with open(config_path) as f:
                data = json.load(f)

            # Check essential keys
            essential = ["llm", "workspace"]
            missing_keys = [k for k in essential if k not in data]
            if missing_keys:
                self._results.append(DiagnosticResult(
                    check_id="config_file",
                    name="Configuration",
                    status="warning",
                    message=f"Missing keys: {', '.join(missing_keys)}",
                ))
            else:
                self._results.append(DiagnosticResult(
                    check_id="config_file",
                    name="Configuration",
                    status="ok",
                    message="config.json valid",
                ))
        except Exception as e:
            self._results.append(DiagnosticResult(
                check_id="config_file",
                name="Configuration",
                status="error",
                message=f"Invalid JSON: {str(e)[:50]}",
            ))

    async def _check_env_vars(self) -> None:
        """Check for required environment variables."""
        optional_vars = {
            "OPENAI_API_KEY": "OpenAI",
            "ANTHROPIC_API_KEY": "Anthropic",
            "GOOGLE_API_KEY": "Google AI",
            "BRAVE_API_KEY": "Brave Search",
        }

        found = []
        missing = []
        for var, name in optional_vars.items():
            if os.environ.get(var):
                found.append(name)
            else:
                missing.append(name)

        if not found:
            self._results.append(DiagnosticResult(
                check_id="env_vars",
                name="API Keys (ENV)",
                status="warning",
                message="No API keys in environment (may be in config.json)",
            ))
        else:
            self._results.append(DiagnosticResult(
                check_id="env_vars",
                name="API Keys (ENV)",
                status="ok",
                message=f"Found: {', '.join(found)}",
            ))

    async def _check_auth_keys(self) -> None:
        """Check if API keys are configured and valid format."""
        if not self._config:
            self._results.append(DiagnosticResult(
                check_id="auth_keys",
                name="Auth Profiles",
                status="warning",
                message="No config available to check auth profiles",
            ))
            return

        # Check LLM config
        llm_config = getattr(self._config, 'llm', None) or {}
        if isinstance(llm_config, dict):
            api_key = llm_config.get("api_key", "")
            if api_key and len(api_key) > 10:
                self._results.append(DiagnosticResult(
                    check_id="auth_keys",
                    name="Auth Profiles",
                    status="ok",
                    message="API key configured (format valid)",
                ))
            else:
                self._results.append(DiagnosticResult(
                    check_id="auth_keys",
                    name="Auth Profiles",
                    status="error",
                    message="No valid API key found in config",
                    fixable=False,
                ))

    async def _check_database(self) -> None:
        """Check database state."""
        db_path = self._workspace / "data" / "kabot.db"
        if not db_path.exists():
            # Check alternative locations
            alt_path = self._workspace / "kabot.db"
            if alt_path.exists():
                db_path = alt_path
            else:
                self._results.append(DiagnosticResult(
                    check_id="database",
                    name="Database",
                    status="warning",
                    message="No database file found (will be created on first use)",
                ))
                return

        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            conn.close()

            self._results.append(DiagnosticResult(
                check_id="database",
                name="Database",
                status="ok",
                message=f"{table_count} tables, {db_path.stat().st_size / 1024:.1f} KB",
            ))
        except Exception as e:
            self._results.append(DiagnosticResult(
                check_id="database",
                name="Database",
                status="error",
                message=f"Error: {str(e)[:50]}",
                fixable=True,
            ))

    async def _check_workspace(self) -> None:
        """Verify workspace directory structure."""
        required_dirs = ["profiles", "skills"]
        missing = [d for d in required_dirs if not (self._workspace / d).exists()]

        if missing:
            self._results.append(DiagnosticResult(
                check_id="workspace",
                name="Workspace",
                status="warning",
                message=f"Missing dirs: {', '.join(missing)}",
                fixable=True,
            ))
        else:
            self._results.append(DiagnosticResult(
                check_id="workspace",
                name="Workspace",
                status="ok",
                message=str(self._workspace),
            ))

    async def _attempt_fix(self, result: DiagnosticResult) -> None:
        """Attempt to auto-fix a failed check."""
        logger.info(f"Attempting auto-fix for: {result.check_id}")

        if result.check_id == "dependencies":
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                    cwd=str(self._workspace),
                    capture_output=True,
                    timeout=120,
                )
                result.fix_applied = True
                result.message += " → Fixed: reinstalled dependencies"
            except Exception as e:
                result.message += f" → Fix failed: {str(e)[:30]}"

        elif result.check_id == "workspace":
            try:
                for d in ["profiles", "skills"]:
                    (self._workspace / d).mkdir(exist_ok=True)
                result.fix_applied = True
                result.message += " → Fixed: created missing dirs"
            except Exception as e:
                result.message += f" → Fix failed: {str(e)[:30]}"

    def _format_report(self) -> str:
        """Format diagnostic results into a readable report."""
        status_icons = {
            "ok": "✅",
            "warning": "⚠️",
            "error": "❌",
        }

        lines = [
            "🩺 *Kabot Doctor Report*",
            "─────────────────────────",
        ]

        ok_count = sum(1 for r in self._results if r.status == "ok")
        warn_count = sum(1 for r in self._results if r.status == "warning")
        err_count = sum(1 for r in self._results if r.status == "error")

        for result in self._results:
            icon = status_icons.get(result.status, "❓")
            fix_badge = " 🔧" if result.fix_applied else ""
            lines.append(f"  {icon} *{result.name}*: {result.message}{fix_badge}")

        lines.extend([
            "",
            f"─────────────────────────",
            f"  ✅ {ok_count} OK  ⚠️ {warn_count} Warnings  ❌ {err_count} Errors",
        ])

        if err_count == 0 and warn_count == 0:
            lines.append("\n🎉 All checks passed! System is healthy.")
        elif err_count > 0:
            lines.append("\n💡 Run `/doctor fix` to attempt auto-repairs.")

        return "\n".join(lines)
