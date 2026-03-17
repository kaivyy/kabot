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
_ROUTING_DOCTOR_TOOL_SET = {
    "weather",
    "cron",
    "get_system_info",
    "cleanup_system",
    "speedtest",
    "get_process_memory",
    "stock",
    "crypto",
    "server_monitor",
    "web_search",
    "check_update",
    "system_update",
}


class _RoutingDoctorTools:
    """Minimal tool registry probe for execution guard validation."""

    def __init__(self, tool_names: set[str]):
        self._tool_names = set(tool_names)

    def has(self, name: str) -> bool:
        return str(name or "").strip() in self._tool_names


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
            "memory": self._memory_diagnostic(),
            "dependencies": self.check_dependencies(),
            "connectivity": asyncio.run(self.check_connectivity()),
            "skills": self.check_skills(),
        }

    def _memory_diagnostic(self) -> dict[str, Any]:
        """Inspect the configured memory backend and current retrieval mode."""
        try:
            from kabot.memory.memory_factory import MemoryFactory
        except Exception as exc:
            return {"status": "error", "detail": f"memory_factory_unavailable: {exc}"}

        config = self.config
        if config is None:
            return {"status": "error", "detail": "config_unavailable"}

        try:
            config_dict = config.model_dump() if hasattr(config, "model_dump") else config.dict()
        except Exception as exc:
            return {"status": "error", "detail": f"config_dump_failed: {exc}"}

        runtime_perf = getattr(getattr(config, "runtime", None), "performance", None)
        lazy_probe = bool(getattr(runtime_perf, "defer_memory_warmup", False))
        try:
            memory = MemoryFactory.create(config_dict, self.workspace, lazy_probe=lazy_probe)
        except Exception as exc:
            return {"status": "error", "detail": f"memory_init_failed: {exc}"}

        stats: dict[str, Any] = {}
        health: dict[str, Any] = {}

        get_stats = getattr(memory, "get_stats", None)
        if callable(get_stats):
            try:
                raw_stats = get_stats()
            except Exception:
                raw_stats = {}
            if isinstance(raw_stats, dict):
                stats = dict(raw_stats)

        health_check = getattr(memory, "health_check", None)
        if callable(health_check):
            try:
                raw_health = health_check()
            except Exception:
                raw_health = {}
            if isinstance(raw_health, dict):
                health = dict(raw_health)

        return {
            "status": str(health.get("status") or "ok"),
            "backend": str(stats.get("backend") or health.get("backend") or "").strip(),
            "retrieval_mode": str(stats.get("retrieval_mode") or health.get("retrieval_mode") or "").strip(),
            "embedding_provider": str(stats.get("embedding_provider") or health.get("embedding_provider") or "").strip(),
            "embedding_model": str(stats.get("embedding_model") or health.get("embedding_model") or "").strip(),
            "lazy_probe": bool(stats.get("lazy_probe", health.get("lazy_probe", False))),
            "hybrid_loaded": bool(stats.get("hybrid_loaded", health.get("hybrid_loaded", False))),
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

    def run_routing_diagnostic(self) -> dict[str, Any]:
        """
        Run deterministic routing and tool-guard sanity checks.

        Focuses on high-frequency production prompts (news/weather/stock/crypto)
        plus API-skill-like guard paths (image/TTS) to catch regressions before
        deploy/restart.
        """
        from types import SimpleNamespace

        from kabot.agent.cron_fallback_nlp import required_tool_for_query
        from kabot.agent.loop_core.execution_runtime import _tool_call_intent_mismatch_reason
        from kabot.bus.events import InboundMessage

        route_cases: list[tuple[str, str | None]] = [
            ("news iran israel 2026 now", "web_search"),
            ("latest war news iran israel now", "web_search"),
            ("weather jakarta now", "weather"),
            ("temperature cilacap now", "weather"),
            ("BBRI.JK BBCA.JK BMRI.JK ADRO.JK", "stock"),
            ("btc now", "crypto"),
            ("eth price now", "crypto"),
            ("remind me in 2 minutes to eat", "cron"),
            ("check update kabot", "check_update"),
            ("system update kabot", "system_update"),
            ("ram capacity", "get_system_info"),
            ("process memory now", "get_process_memory"),
            ("cleanup temp files now", "cleanup_system"),
            ("speedtest now", "speedtest"),
            ("server monitor now", "server_monitor"),
            ("read file config.json", None),
            ("stop talking about stocks", None),
            ("hello there", None),
            ("make an image of a car in a forest", None),
            ("read this text aloud", None),
        ]

        route_results: list[dict[str, Any]] = []
        for prompt, expected in route_cases:
            got = required_tool_for_query(
                question=prompt,
                has_weather_tool=True,
                has_cron_tool=True,
                has_system_info_tool=True,
                has_cleanup_tool=True,
                has_speedtest_tool=True,
                has_process_memory_tool=True,
                has_stock_tool=True,
                has_crypto_tool=True,
                has_server_monitor_tool=True,
                has_web_search_tool=True,
                has_check_update_tool=True,
                has_system_update_tool=True,
            )
            route_results.append(
                {
                    "prompt": prompt,
                    "expected": expected,
                    "got": got,
                    "pass": got == expected,
                }
            )

        loop_probe = SimpleNamespace(tools=_RoutingDoctorTools(_ROUTING_DOCTOR_TOOL_SET))
        guard_cases: list[tuple[str, str, bool]] = [
            ("baca file config.json", "stock", True),
            ("stop bahas saham", "stock", True),
            ("halo", "cron", True),
            ("harga btc terbaru", "image_gen", True),
            ("buatkan gambar mobil di hutan", "image_gen", True),
            ("tolong bacakan teks ini jadi suara", "tts", True),
        ]
        guard_results: list[dict[str, Any]] = []
        for prompt, tool_name, should_block in guard_cases:
            msg = InboundMessage(channel="telegram", chat_id="doctor", sender_id="doctor", content=prompt)
            reason = _tool_call_intent_mismatch_reason(loop_probe, msg, tool_name)
            blocked = reason is not None
            guard_results.append(
                {
                    "prompt": prompt,
                    "tool": tool_name,
                    "should_block": should_block,
                    "blocked": blocked,
                    "reason": reason,
                    "pass": blocked == should_block,
                }
            )

        route_passed = sum(1 for item in route_results if item.get("pass"))
        guard_passed = sum(1 for item in guard_results if item.get("pass"))
        return {
            "routing": {
                "total": len(route_results),
                "passed": route_passed,
                "failed": len(route_results) - route_passed,
                "cases": route_results,
            },
            "guard": {
                "total": len(guard_results),
                "passed": guard_passed,
                "failed": len(guard_results) - guard_passed,
                "cases": guard_results,
            },
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

        memory = report.get("memory", {}) if isinstance(report.get("memory"), dict) else {}
        memory_text = (
            f"- status: {memory.get('status', 'unknown')}\n"
            f"- backend: {memory.get('backend', '')}\n"
            f"- retrieval_mode: {memory.get('retrieval_mode', '')}\n"
            f"- embedding_provider: {memory.get('embedding_provider', '')}\n"
            f"- embedding_model: {memory.get('embedding_model', '')}\n"
            f"- lazy_probe: {memory.get('lazy_probe', False)}\n"
            f"- hybrid_loaded: {memory.get('hybrid_loaded', False)}"
        )
        console.print(Panel(memory_text, title=" Memory Stack ", border_style="dim", box=box.ROUNDED))

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

    def render_routing_report(self) -> None:
        """Render deterministic routing + guard sanity results."""
        report = self.run_routing_diagnostic()
        routing = report["routing"]
        guard = report["guard"]

        console.print("\n[bold cyan]+ Kabot doctor routing[/bold cyan]")
        summary_text = (
            f"- routing: {routing['passed']}/{routing['total']} passed\n"
            f"- guard: {guard['passed']}/{guard['total']} passed\n"
            f"- generated_at: {report.get('generated_at')}"
        )
        summary_style = "green" if routing["failed"] == 0 and guard["failed"] == 0 else "yellow"
        console.print(Panel(summary_text, title=" Routing Sanity Summary ", border_style=summary_style, box=box.ROUNDED))

        failed_lines: list[str] = []
        for item in routing["cases"]:
            if item.get("pass"):
                continue
            failed_lines.append(
                f"- route FAIL | expected={item.get('expected')!r} got={item.get('got')!r} | {item.get('prompt')}"
            )
        for item in guard["cases"]:
            if item.get("pass"):
                continue
            failed_lines.append(
                f"- guard FAIL | tool={item.get('tool')} should_block={item.get('should_block')} "
                f"blocked={item.get('blocked')} reason={item.get('reason')!r} | {item.get('prompt')}"
            )

        if failed_lines:
            detail = "\n".join(failed_lines[:20])
            console.print(Panel(detail, title=" Failed Cases ", border_style="red", box=box.ROUNDED))
            console.print("[yellow]Tip: Fix routing/guard regressions before deploy or restart.[/yellow]")
        else:
            console.print("[green]Routing sanity checks passed. Safe to continue deploy/restart flow.[/green]")
