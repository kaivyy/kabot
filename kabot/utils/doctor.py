"""Kabot Doctor: diagnostic and self-healing engine."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

import httpx
from rich import box
from rich.console import Console
from rich.panel import Panel

from kabot.config.loader import get_agent_dir, get_global_data_dir
from kabot.utils.environment import detect_runtime_environment, recommended_gateway_mode

console = Console()


class KabotDoctor:
    """Diagnostic engine to verify system health and integrity."""

    def __init__(self, agent_id: str = "main"):
        self.agent_id = agent_id
        self.global_dir = get_global_data_dir()
        self.agent_dir = get_agent_dir(agent_id)

    def run_full_diagnostic(self, fix: bool = False) -> dict[str, Any]:
        """Execute health checks and optionally fix issues."""
        integrity = self.check_state_integrity()

        if fix:
            self.apply_fixes(integrity)
            integrity = self.check_state_integrity()

        return {
            "integrity": integrity,
            "environment": self.check_environment_matrix(),
            "dependencies": self.check_dependencies(),
            "connectivity": asyncio.run(self.check_connectivity()),
            "skills": self.check_skills(),
        }

    def _managed_directories(self) -> list[tuple[str, Path]]:
        return [
            ("Global Root", self.global_dir),
            ("Agent Root", self.agent_dir),
            ("Sessions", self.agent_dir / "sessions"),
            ("Memory", self.agent_dir / "memory_db"),
            ("Workspace", self.agent_dir / "workspace"),
            ("Logs", self.agent_dir / "logs"),
            ("Workspace Plugins", self.agent_dir / "workspace" / "plugins"),
            ("Workspace Temp", self.agent_dir / "workspace" / "tmp"),
        ]

    def check_state_integrity(self) -> list[dict[str, Any]]:
        """Verify essential directories exist and are writable."""
        checks: list[dict[str, Any]] = []
        for name, path in self._managed_directories():
            status = "OK"
            detail = f"Path: {path}"
            if not path.exists():
                status = "CRITICAL"
                detail = f"Missing: {path}"
            elif not os.access(path, os.W_OK):
                status = "WARN"
                detail = f"No write access: {path}"

            checks.append({"item": name, "status": status, "detail": detail, "path": path})
        return checks

    def apply_fixes(self, integrity_report: list[dict[str, Any]]) -> None:
        """Fix critical integrity issues by creating missing folders."""
        for issue in integrity_report:
            if issue.get("status") != "CRITICAL":
                continue
            path = issue.get("path")
            if not isinstance(path, Path):
                continue
            try:
                path.mkdir(parents=True, exist_ok=True)
                console.print(f"  [green]OK[/green] Created {issue['item']} directory")
            except Exception as exc:
                console.print(f"  [red]FAIL[/red] Could not create {issue['item']}: {exc}")

        # Ensure all managed directories exist after fix pass.
        for _, path in self._managed_directories():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

    def check_environment_matrix(self) -> list[dict[str, Any]]:
        """Run environment-level checks for service/runtime operations."""
        runtime = detect_runtime_environment()
        gateway_mode = recommended_gateway_mode(runtime)

        checks: list[dict[str, Any]] = [
            {"item": "Platform", "status": "OK", "detail": runtime.platform},
            {"item": "Recommended Gateway Mode", "status": "OK", "detail": gateway_mode},
            {"item": "Headless Runtime", "status": "OK" if runtime.is_headless else "INFO", "detail": str(runtime.is_headless)},
        ]

        if runtime.is_wsl:
            checks.append(
                {
                    "item": "WSL",
                    "status": "WARN",
                    "detail": "WSL detected; prefer remote gateway mode for callback/oauth flows.",
                }
            )

        if runtime.is_termux:
            has_sv = shutil.which("sv") is not None
            checks.append(
                {
                    "item": "Termux Services",
                    "status": "OK" if has_sv else "WARN",
                    "detail": "sv command found" if has_sv else "termux-services package missing",
                }
            )

        if runtime.is_windows:
            has_schtasks = shutil.which("schtasks") is not None
            checks.append(
                {
                    "item": "Task Scheduler",
                    "status": "OK" if has_schtasks else "WARN",
                    "detail": "schtasks found" if has_schtasks else "schtasks not found",
                }
            )
        elif runtime.is_macos:
            has_launchctl = shutil.which("launchctl") is not None
            checks.append(
                {
                    "item": "launchd",
                    "status": "OK" if has_launchctl else "WARN",
                    "detail": "launchctl found" if has_launchctl else "launchctl not found",
                }
            )
        elif runtime.is_linux and not runtime.is_termux:
            has_systemctl = shutil.which("systemctl") is not None
            checks.append(
                {
                    "item": "systemd",
                    "status": "OK" if has_systemctl else "WARN",
                    "detail": "systemctl found" if has_systemctl else "systemctl not found",
                }
            )

        return checks

    def check_dependencies(self) -> list[dict[str, Any]]:
        checks = []
        bins = [
            ("Python", "python", True),
            ("NPM", "npm", False),
            ("Docker", "docker", False),
            ("Playwright", "playwright", False),
        ]
        for name, cmd, required in bins:
            path = shutil.which(cmd)
            status = "OK" if path else ("CRITICAL" if required else "OPTIONAL")
            msg = f"Found at {path}" if path else f"{cmd} not found"
            checks.append({"item": name, "status": status, "detail": msg})
        return checks

    async def check_connectivity(self) -> list[dict[str, Any]]:
        checks = []
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.get("https://google.com")
            checks.append({"item": "Internet", "status": "OK", "detail": "Connected"})
        except Exception:
            checks.append({"item": "Internet", "status": "CRITICAL", "detail": "Offline"})
        return checks

    def check_skills(self) -> dict[str, Any]:
        from kabot.agent.loop import AgentLoop
        from kabot.bus.queue import MessageBus
        from kabot.providers.litellm_provider import LiteLLMProvider

        agent = AgentLoop(bus=MessageBus(), provider=LiteLLMProvider(api_key="none"), workspace=self.agent_dir)
        eligible: list[str] = []
        missing: list[dict[str, str]] = []

        for name in agent.tools.list_tools():
            tool = agent.tools.get(name)
            ok, err = tool.check_requirements()
            if ok:
                eligible.append(name)
            else:
                missing.append({"name": name, "error": err})
        return {"eligible": eligible, "missing": missing}

    def render_report(self, fix: bool = False) -> None:
        """Render diagnostic report."""
        report = self.run_full_diagnostic(fix=fix)

        console.print("\n[bold cyan]+ Kabot doctor[/bold cyan]")

        integrity_text = ""
        for item in report["integrity"]:
            color = "green" if item["status"] == "OK" else "red"
            integrity_text += f"[{color}]- {item['status']}: {item['item']} -> {item['detail']}[/{color}]\n"
        console.print(Panel(integrity_text.strip(), title=" State Integrity ", border_style="dim", box=box.ROUNDED))

        env_text = ""
        for item in report["environment"]:
            color = "green" if item["status"] in {"OK", "INFO"} else "yellow"
            env_text += f"[{color}]- {item['status']}: {item['item']} -> {item['detail']}[/{color}]\n"
        console.print(Panel(env_text.strip(), title=" Environment Matrix ", border_style="dim", box=box.ROUNDED))

        skills_text = f"Eligible: {len(report['skills']['eligible'])}\n"
        skills_text += f"Missing: {len(report['skills']['missing'])}\n"
        for missing in report["skills"]["missing"]:
            skills_text += f"[red]- {missing['name']}: {missing['error']}[/red]\n"
        console.print(Panel(skills_text.strip(), title=" Skills Status ", border_style="dim", box=box.ROUNDED))

        if not fix and any(item["status"] == "CRITICAL" for item in report["integrity"]):
            console.print("[yellow]Tip: Run 'kabot doctor --fix' to automatically create missing directories.[/yellow]\n")
