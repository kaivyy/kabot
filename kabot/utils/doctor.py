"""Kabot Doctor: Diagnostic and self-healing engine."""

import os
import shutil
import asyncio
import httpx
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.prompt import Confirm

from kabot.config.loader import get_global_data_dir, get_agent_dir

console = Console()

class KabotDoctor:
    """Diagnostic engine to verify system health and integrity."""

    def __init__(self, agent_id: str = "main"):
        self.agent_id = agent_id
        self.global_dir = get_global_data_dir()
        self.agent_dir = get_agent_dir(agent_id)

    def run_full_diagnostic(self, fix: bool = False) -> Dict[str, Any]:
        """Execute health checks and optionally fix issues."""
        integrity = self.check_state_integrity()
        
        # If fix is requested, attempt to repair CRITICAL issues
        if fix:
            self.apply_fixes(integrity)
            # Re-check after fixes
            integrity = self.check_state_integrity()

        results = {
            "integrity": integrity,
            "dependencies": self.check_dependencies(),
            "connectivity": asyncio.run(self.check_connectivity()),
            "skills": self.check_skills()
        }
        return results

    def check_state_integrity(self) -> List[Dict[str, Any]]:
        """Verify essential directories exist."""
        checks = []
        folders = [
            ("Global Root", self.global_dir),
            ("Agent Root", self.agent_dir),
            ("Sessions", self.agent_dir / "sessions"),
            ("Memory", self.agent_dir / "memory_db"),
            ("Workspace", self.agent_dir / "workspace")
        ]
        
        for name, path in folders:
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

    def apply_fixes(self, integrity_report: List[Dict[str, Any]]):
        """Fix CRITICAL integrity issues by creating missing folders."""
        for issue in integrity_report:
            if issue["status"] == "CRITICAL":
                path = issue["path"]
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    console.print(f"  [green]✓ Fixed: Created {issue['item']} directory[/green]")
                except Exception as e:
                    console.print(f"  [red]✗ Failed to fix {issue['item']}: {e}[/red]")

    def check_dependencies(self) -> List[Dict[str, Any]]:
        checks = []
        bins = [
            ("Python", "python", True),
            ("NPM", "npm", False),
            ("Docker", "docker", False),
            ("Playwright", "playwright", False)
        ]
        for name, cmd, required in bins:
            path = shutil.which(cmd)
            status = "OK" if path else ("CRITICAL" if required else "OPTIONAL")
            msg = f"Found at {path}" if path else f"{cmd} not found"
            checks.append({"item": name, "status": status, "detail": msg})
        return checks

    async def check_connectivity(self) -> List[Dict[str, Any]]:
        checks = []
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.get("https://google.com")
            checks.append({"item": "Internet", "status": "OK", "detail": "Connected"})
        except Exception:
            checks.append({"item": "Internet", "status": "CRITICAL", "detail": "Offline"})
        return checks

    def check_skills(self) -> Dict[str, Any]:
        from kabot.agent.tools.registry import ToolRegistry
        from kabot.agent.loop import AgentLoop
        from kabot.bus.queue import MessageBus
        from kabot.providers.litellm_provider import LiteLLMProvider
        
        agent = AgentLoop(bus=MessageBus(), provider=LiteLLMProvider(api_key="none"), workspace=self.agent_dir)
        eligible, missing = [], []
        
        for name in agent.tools.list_tools():
            tool = agent.tools.get(name)
            ok, err = tool.check_requirements()
            if ok: eligible.append(name)
            else: missing.append({"name": name, "error": err})
        return {"eligible": eligible, "missing": missing}

    def render_report(self, fix: bool = False):
        """Render the diagnostic report with Clack aesthetic."""
        report = self.run_full_diagnostic(fix=fix)
        
        console.print("\n[bold cyan]┌  Kabot doctor[/bold cyan]")
        
        # Integrity
        content = ""
        for c in report["integrity"]:
            color = "green" if c["status"] == "OK" else "red"
            content += f"[{color}]- {c['status']}: {c['item']} -> {c['detail']}[/{color}]\n"
        console.print("│")
        console.print(f"◇  {Panel(content.strip(), title=' State Integrity ', border_style='dim', box=box.ROUNDED)}")
        
        # Skills
        content = f"Eligible: {len(report['skills']['eligible'])}\n"
        content += f"Missing: {len(report['skills']['missing'])}\n"
        for m in report['skills']['missing']:
            content += f"[red]- {m['name']}: {m['error']}[/red]\n"
        console.print("│")
        console.print(f"◇  {Panel(content.strip(), title=' Skills Status ', border_style='dim', box=box.ROUNDED)}")
        
        console.print("└\n")
        if not fix and any(c["status"] == "CRITICAL" for c in report["integrity"]):
            console.print("[yellow]Tip: Run 'kabot doctor --fix' to automatically create missing directories.[/yellow]\n")
