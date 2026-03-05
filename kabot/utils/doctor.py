"""Kabot Doctor: diagnostic and self-healing engine."""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from rich import box
from rich.console import Console
from rich.panel import Panel

from kabot.agent.agent_scope import resolve_agent_workspace
from kabot.config.loader import get_agent_dir, get_global_data_dir, load_config
from kabot.utils.bootstrap_parity import (
    BootstrapParityPolicy,
    apply_bootstrap_fixes,
    check_bootstrap_parity,
    policy_from_config,
)
from kabot.utils.environment import detect_runtime_environment, recommended_gateway_mode
from kabot.utils.soak_gate import evaluate_alpha_soak_gate, load_soak_metrics

console = Console()
_INSTANCE_BRIDGE_REQUIRED_TYPES = {
    "whatsapp",
    "signal",
    "matrix",
    "teams",
    "google_chat",
    "mattermost",
    "webex",
    "line",
}
_LEGACY_BRIDGE_REQUIRED_TYPES = {"whatsapp"}


class KabotDoctor:
    """Diagnostic engine to verify system health and integrity."""

    def __init__(self, agent_id: str = "main"):
        self.agent_id = agent_id
        self.global_dir = get_global_data_dir()
        self.agent_dir = get_agent_dir(agent_id)
        self.config = self._load_config_safe()
        self.workspace = self._resolve_workspace()
        self.bootstrap_policy = self._resolve_bootstrap_policy()

    def _load_config_safe(self) -> Any | None:
        try:
            return load_config()
        except Exception:
            return None

    def _resolve_workspace(self) -> Path:
        if self.config is not None:
            try:
                return resolve_agent_workspace(self.config, self.agent_id)
            except Exception:
                pass
        return self.agent_dir / "workspace"

    def _resolve_bootstrap_policy(self) -> BootstrapParityPolicy:
        return policy_from_config(self.config)

    def run_full_diagnostic(self, fix: bool = False, sync_bootstrap: bool = False) -> dict[str, Any]:
        """Execute health checks and optionally fix issues."""
        integrity = self.check_state_integrity()
        bootstrap_parity = self.check_bootstrap_parity()

        if fix:
            self.apply_fixes(integrity, bootstrap_parity, sync_bootstrap=sync_bootstrap)
            integrity = self.check_state_integrity()
            bootstrap_parity = self.check_bootstrap_parity()

        return {
            "integrity": integrity,
            "bootstrap_parity": bootstrap_parity,
            "environment": self.check_environment_matrix(),
            "dependencies": self.check_dependencies(),
            "connectivity": asyncio.run(self.check_connectivity()),
            "skills": self.check_skills(),
        }

    def run_parity_diagnostic(self) -> dict[str, Any]:
        """Run parity-focused diagnostics required for 0.5.8 ops gate."""
        return {
            "runtime_resilience": self._runtime_resilience_status(),
            "fallback_state_machine": self._fallback_state_machine_status(),
            "adapter_registry": self._adapter_registry_status(),
            "migration_status": self._migration_status(),
            "bridge_health": self._check_bridge_health(),
            "skills_precedence": self._skills_precedence_status(),
            "soak_gate": self._soak_gate_status(),
            "generated_at": datetime.now().isoformat(),
        }

    def _managed_directories(self) -> list[tuple[str, Path]]:
        return [
            ("Global Root", self.global_dir),
            ("Agent Root", self.agent_dir),
            ("Sessions", self.agent_dir / "sessions"),
            ("Memory", self.agent_dir / "memory_db"),
            ("Workspace", self.workspace),
            ("Logs", self.agent_dir / "logs"),
            ("Workspace Plugins", self.workspace / "plugins"),
            ("Workspace Temp", self.workspace / "tmp"),
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

    def check_bootstrap_parity(self) -> list[dict[str, Any]]:
        """Check bootstrap files for workspace parity."""
        return check_bootstrap_parity(self.workspace, self.bootstrap_policy)

    def apply_fixes(
        self,
        integrity_report: list[dict[str, Any]],
        bootstrap_report: list[dict[str, Any]] | None = None,
        *,
        sync_bootstrap: bool = False,
    ) -> None:
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

        parity_issues = bootstrap_report if bootstrap_report is not None else self.check_bootstrap_parity()
        if parity_issues:
            changes = apply_bootstrap_fixes(
                self.workspace,
                self.bootstrap_policy,
                sync_mismatch=sync_bootstrap,
            )
            for change in changes:
                console.print(f"  [green]OK[/green] {change}")

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

        for name in agent.tools.tool_names:
            tool = agent.tools.get(name)
            ok, err = tool.check_requirements()
            if ok:
                eligible.append(name)
            else:
                missing.append({"name": name, "error": err})
        return {"eligible": eligible, "missing": missing}

    def _runtime_resilience_status(self) -> dict[str, Any]:
        runtime_cfg = getattr(self.config, "runtime", None)
        resilience = getattr(runtime_cfg, "resilience", None)
        observability = getattr(runtime_cfg, "observability", None)
        quotas = getattr(runtime_cfg, "quotas", None)
        return {
            "enabled": bool(getattr(resilience, "enabled", True)),
            "dedupe_tool_calls": bool(getattr(resilience, "dedupe_tool_calls", True)),
            "max_model_attempts_per_turn": int(getattr(resilience, "max_model_attempts_per_turn", 4)),
            "max_tool_retry_per_turn": int(getattr(resilience, "max_tool_retry_per_turn", 1)),
            "observability_enabled": bool(getattr(observability, "enabled", True)),
            "quotas_enabled": bool(getattr(quotas, "enabled", False)),
        }

    def _fallback_state_machine_status(self) -> dict[str, Any]:
        from kabot.agent.loop_core import execution_runtime

        return {
            "call_llm_with_fallback_present": callable(getattr(execution_runtime, "call_llm_with_fallback", None)),
            "process_tool_calls_present": callable(getattr(execution_runtime, "process_tool_calls", None)),
            "error_classifier_present": callable(getattr(execution_runtime, "_classify_runtime_error", None)),
        }

    def _adapter_registry_status(self) -> dict[str, Any]:
        from kabot.bus.queue import MessageBus
        from kabot.channels.adapters import AdapterRegistry

        feature_flags = {}
        if self.config is not None:
            feature_flags = dict(getattr(getattr(self.config, "channels", None), "adapters", {}) or {})
        registry = AdapterRegistry(feature_flags=feature_flags)
        statuses = registry.list_status()
        status_by_key = {s.key: s for s in statuses}
        total = len(statuses)
        enabled = sum(1 for s in statuses if s.enabled)
        production = sum(1 for s in statuses if s.production)
        experimental = sum(1 for s in statuses if s.experimental)
        placeholder_like = [s.key for s in statuses if "(planned)" in s.description or "(experimental)" in s.description]
        instance_channels: list[dict[str, Any]] = []
        instance_reasons: dict[str, int] = {}
        configured_instances = 0
        if self.config is not None:
            for instance in getattr(self.config.channels, "instances", []) or []:
                configured_instances += 1
                instance_type = str(getattr(instance, "type", "") or "").strip()
                instance_id = str(getattr(instance, "id", "") or "").strip()
                adapter_status = status_by_key.get(instance_type)
                adapter_enabled = bool(adapter_status.enabled) if adapter_status else False
                constructable = False
                if adapter_enabled:
                    try:
                        constructable = (
                            registry.create_instance_channel(
                                instance=instance,
                                config=self.config,
                                bus=MessageBus(),
                                session_manager=None,
                            )
                            is not None
                        )
                    except Exception:
                        constructable = False
                cfg = getattr(instance, "config", {}) or {}
                bridge_url = str(cfg.get("bridge_url", "")).strip() if isinstance(cfg, dict) else ""
                reachable = self._bridge_url_reachable(bridge_url) if bridge_url else None
                reasons: list[str] = []
                if adapter_status is None:
                    reasons.append("adapter_not_registered")
                elif not adapter_enabled:
                    reasons.append("adapter_disabled_by_flag")
                elif not constructable:
                    reasons.append("adapter_init_failed")
                if instance_type in _INSTANCE_BRIDGE_REQUIRED_TYPES:
                    if not bridge_url:
                        reasons.append("missing_bridge_url")
                    elif reachable is False:
                        reasons.append("bridge_unreachable")
                status = "ready" if not reasons else "not_ready"
                for reason in reasons:
                    instance_reasons[reason] = instance_reasons.get(reason, 0) + 1
                instance_channels.append(
                    {
                        "key": f"{instance_type}:{instance_id}" if instance_type and instance_id else instance_id or instance_type,
                        "type": instance_type,
                        "id": instance_id,
                        "adapter_enabled": adapter_enabled,
                        "constructable": constructable,
                        "bridge_url": bridge_url or None,
                        "reachable": reachable,
                        "status": status,
                        "reasons": reasons,
                    }
                )
        legacy_channels: list[dict[str, Any]] = []
        legacy_reasons: dict[str, int] = {}
        if self.config is not None:
            for status in statuses:
                if not status.supports_legacy:
                    continue
                legacy_cfg = getattr(self.config.channels, status.key, None)
                legacy_enabled = bool(getattr(legacy_cfg, "enabled", False)) if legacy_cfg else False
                if not legacy_enabled:
                    continue
                constructable = False
                if status.enabled:
                    try:
                        constructable = (
                            registry.create_legacy_channel(
                                key=status.key,
                                config=self.config,
                                bus=MessageBus(),
                                session_manager=None,
                            )
                            is not None
                        )
                    except Exception:
                        constructable = False
                bridge_url: str | None = None
                reachable: bool | None = None
                if status.key in _LEGACY_BRIDGE_REQUIRED_TYPES and legacy_cfg is not None:
                    bridge_url = str(getattr(legacy_cfg, "bridge_url", "") or "").strip() or None
                    if bridge_url:
                        reachable = self._bridge_url_reachable(bridge_url)
                reasons: list[str] = []
                if not status.enabled:
                    reasons.append("adapter_disabled_by_flag")
                elif not constructable:
                    reasons.append("adapter_init_failed")
                if status.key in _LEGACY_BRIDGE_REQUIRED_TYPES:
                    if not bridge_url:
                        reasons.append("missing_bridge_url")
                    elif reachable is False:
                        reasons.append("bridge_unreachable")
                health = "ready" if not reasons else "not_ready"
                for reason in reasons:
                    legacy_reasons[reason] = legacy_reasons.get(reason, 0) + 1
                legacy_channels.append(
                    {
                        "key": status.key,
                        "adapter_enabled": bool(status.enabled),
                        "constructable": constructable,
                        "bridge_url": bridge_url,
                        "reachable": reachable,
                        "status": health,
                        "reasons": reasons,
                    }
                )
        ready_instances = sum(1 for item in instance_channels if item.get("status") == "ready")
        ready_legacy = sum(1 for item in legacy_channels if item.get("status") == "ready")
        return {
            "total": total,
            "enabled": enabled,
            "production": production,
            "experimental": experimental,
            "placeholder_like": placeholder_like,
            "configured_instances": configured_instances,
            "ready_instances": ready_instances,
            "not_ready_instances": max(0, configured_instances - ready_instances),
            "ready_legacy": ready_legacy,
            "not_ready_legacy": max(0, len(legacy_channels) - ready_legacy),
            "instance_reason_counts": instance_reasons,
            "legacy_reason_counts": legacy_reasons,
            "instance_channels": instance_channels,
            "legacy_channels": legacy_channels,
        }

    def _bridge_url_reachable(self, bridge_url: str) -> bool:
        """Check whether a ws/wss URL endpoint is reachable by TCP connect."""
        try:
            parsed = urlparse(bridge_url)
            host = (parsed.hostname or "").strip()
            if not host:
                return False
            if parsed.port is not None:
                port = int(parsed.port)
            elif parsed.scheme == "wss":
                port = 443
            else:
                port = 80
        except Exception:
            return False

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            return sock.connect_ex((host, port)) == 0
        except Exception:
            return False
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _migration_status(self) -> dict[str, Any]:
        cfg = self.config
        if cfg is None:
            return {"loaded": False, "canonical_runtime": False, "canonical_skills": False}
        runtime = getattr(cfg, "runtime", None)
        skills = getattr(cfg, "skills", None)
        security = getattr(cfg, "security", None)
        return {
            "loaded": True,
            "canonical_runtime": bool(runtime and getattr(runtime, "resilience", None) and getattr(runtime, "performance", None)),
            "canonical_observability": bool(runtime and getattr(runtime, "observability", None)),
            "canonical_quotas": bool(runtime and getattr(runtime, "quotas", None)),
            "canonical_skills": bool(skills and hasattr(skills, "entries") and hasattr(skills, "install")),
            "canonical_security": bool(security and getattr(security, "trust_mode", None)),
        }

    def _check_bridge_health(self) -> dict[str, Any]:
        bridge_url = "ws://localhost:3001"
        host = "127.0.0.1"
        port = 3001
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            rc = sock.connect_ex((host, port))
            if rc == 0:
                return {"status": "up", "detail": f"Bridge reachable at {bridge_url}"}
            return {"status": "down", "detail": f"Bridge not listening at {bridge_url}"}
        except Exception as exc:
            return {"status": "down", "detail": f"Bridge health check failed: {exc}"}
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _skills_precedence_status(self) -> dict[str, Any]:
        from kabot.agent.skills import SkillsLoader

        loader = SkillsLoader(self.workspace, skills_config=getattr(self.config, "skills", {}))
        roots = loader._iter_skill_roots()  # parity-report wants explicit precedence visibility
        existing = [str(path) for path in roots if path.exists()]
        return {
            "roots": [str(path) for path in roots],
            "existing_roots": existing,
            "order_note": "higher precedence appears earlier in this list",
        }

    def _soak_gate_status(self) -> dict[str, Any]:
        default_path = self.global_dir / "logs" / "soak_latest.json"
        metrics = load_soak_metrics(default_path)
        if metrics is None:
            return {
                "available": False,
                "path": str(default_path),
                "detail": "No valid soak metrics file found; run soak and write metrics to enable gate summary.",
            }
        gate = evaluate_alpha_soak_gate(metrics)
        return {
            "available": True,
            "path": str(default_path),
            "passed": bool(gate.get("passed")),
            "failures": list(gate.get("failures", [])),
            "checks": list(gate.get("checks", [])),
        }

    def render_report(self, fix: bool = False, sync_bootstrap: bool = False) -> None:
        """Render diagnostic report."""
        report = self.run_full_diagnostic(fix=fix, sync_bootstrap=sync_bootstrap)

        console.print("\n[bold cyan]+ Kabot doctor[/bold cyan]")

        integrity_text = ""
        for item in report["integrity"]:
            color = "green" if item["status"] == "OK" else "red"
            integrity_text += f"[{color}]- {item['status']}: {item['item']} -> {item['detail']}[/{color}]\n"
        console.print(Panel(integrity_text.strip(), title=" State Integrity ", border_style="dim", box=box.ROUNDED))

        parity_text = ""
        for item in report["bootstrap_parity"]:
            status = item["status"]
            color = "green" if status == "OK" else ("yellow" if status == "WARN" else "red")
            parity_text += f"[{color}]- {status}: {item['file']} -> {item['detail']}[/{color}]\n"
        if not parity_text:
            parity_text = "[green]- OK: bootstrap parity checks disabled[/green]"
        console.print(Panel(parity_text.strip(), title=" Bootstrap Parity ", border_style="dim", box=box.ROUNDED))

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
        if not fix and any(item["status"] in {"CRITICAL", "WARN"} for item in report["bootstrap_parity"]):
            console.print(
                "[yellow]Tip: Configure bootstrap baseline and run 'kabot doctor --fix --bootstrap-sync' "
                "to enforce dev/prod prompt parity.[/yellow]\n"
            )

    def render_parity_report(self) -> None:
        """Render a concise parity-focused operations report."""
        report = self.run_parity_diagnostic()

        console.print("\n[bold cyan]+ Kabot parity report[/bold cyan]")

        runtime = report["runtime_resilience"]
        runtime_text = (
            f"- resilience.enabled: {runtime['enabled']}\n"
            f"- dedupe_tool_calls: {runtime['dedupe_tool_calls']}\n"
            f"- max_model_attempts_per_turn: {runtime['max_model_attempts_per_turn']}\n"
            f"- max_tool_retry_per_turn: {runtime['max_tool_retry_per_turn']}\n"
            f"- observability.enabled: {runtime['observability_enabled']}\n"
            f"- quotas.enabled: {runtime['quotas_enabled']}"
        )
        console.print(Panel(runtime_text, title=" Runtime Resilience ", border_style="dim", box=box.ROUNDED))

        fallback = report["fallback_state_machine"]
        fallback_text = "\n".join([f"- {k}: {v}" for k, v in fallback.items()])
        console.print(Panel(fallback_text, title=" Fallback State Machine ", border_style="dim", box=box.ROUNDED))

        adapter = report["adapter_registry"]
        adapter_text = (
            f"- total: {adapter['total']}\n"
            f"- enabled: {adapter['enabled']}\n"
            f"- production: {adapter['production']}\n"
            f"- experimental: {adapter['experimental']}\n"
            f"- placeholder_like: {len(adapter['placeholder_like'])}\n"
            f"- configured_instances: {adapter.get('configured_instances', 0)}\n"
            f"- ready_instances: {adapter.get('ready_instances', 0)}\n"
            f"- not_ready_instances: {adapter.get('not_ready_instances', 0)}\n"
            f"- ready_legacy: {adapter.get('ready_legacy', 0)}\n"
            f"- not_ready_legacy: {adapter.get('not_ready_legacy', 0)}"
        )
        not_ready_items: list[str] = []
        for row in adapter.get("instance_channels", []):
            if row.get("status") != "not_ready":
                continue
            reasons = ", ".join(row.get("reasons", [])) or "unknown"
            not_ready_items.append(f"- {row.get('key')}: {reasons}")
        for row in adapter.get("legacy_channels", []):
            if row.get("status") != "not_ready":
                continue
            reasons = ", ".join(row.get("reasons", [])) or "unknown"
            not_ready_items.append(f"- legacy:{row.get('key')}: {reasons}")
        if not_ready_items:
            adapter_text += "\n- not_ready_details:\n" + "\n".join(not_ready_items)
        console.print(Panel(adapter_text, title=" Adapter Registry ", border_style="dim", box=box.ROUNDED))

        migration = report["migration_status"]
        migration_text = "\n".join([f"- {k}: {v}" for k, v in migration.items()])
        console.print(Panel(migration_text, title=" Migration Status ", border_style="dim", box=box.ROUNDED))

        bridge = report["bridge_health"]
        bridge_text = f"- status: {bridge['status']}\n- detail: {bridge['detail']}"
        console.print(Panel(bridge_text, title=" Bridge Health ", border_style="dim", box=box.ROUNDED))

        skills = report["skills_precedence"]
        roots = "\n".join([f"- {v}" for v in skills.get("roots", [])]) or "- (none)"
        console.print(Panel(roots, title=" Skills Precedence ", border_style="dim", box=box.ROUNDED))

        soak = report["soak_gate"]
        if soak.get("available"):
            soak_text = (
                f"- passed: {soak.get('passed')}\n"
                f"- failures: {', '.join(soak.get('failures', [])) or '(none)'}\n"
                f"- path: {soak.get('path')}"
            )
        else:
            soak_text = (
                f"- available: False\n"
                f"- path: {soak.get('path')}\n"
                f"- detail: {soak.get('detail')}"
            )
        console.print(Panel(soak_text, title=" Soak Gate (Alpha) ", border_style="dim", box=box.ROUNDED))
