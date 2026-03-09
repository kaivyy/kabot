"""SetupWizard section methods: tools_gateway_skills."""

from __future__ import annotations

import os

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt

from kabot.cli.wizard.ui import ClackUI
from kabot.config.skills_settings import (
    iter_skill_env_pairs,
    resolve_install_settings,
    set_skill_entry_env,
)

console = Console()

from kabot.cli.wizard.sections.tools_gateway_skills_helpers import (  # noqa: E402,I001
    skills_checkbox,
    _detect_skill_auth_hint,
    _describe_skill_setup_hint,
    _state_label,
    _bool_label,
    _token_mode_label,
    _is_interactive_tty,
    _is_secret_env_name,
    _collect_skill_env_requirements,
    _load_skill_persona_snippet,
    _load_skill_agents_snippet,
    _extract_skill_capability_summary,
    _build_agents_persona_template,
    _choose_agents_persona_snippet,
    _inject_skill_persona,
    _preview_snippet,
    _extract_skill_candidate_subdirs,
    _normalize_candidate_rows,
    _format_candidate_label,
    _prompt_skill_candidate_subdir,
    _resolve_skill_install_target_dir,
    _wizard_install_external_skill,
    _set_install_settings,
    _install_step_hint,
    _print_manual_install_plan,
    _best_search_provider_from_keys,
)

__all__ = [
    "_best_search_provider_from_keys",
    "_bool_label",
    "_build_agents_persona_template",
    "_choose_agents_persona_snippet",
    "_collect_skill_env_requirements",
    "_configure_gateway",
    "_configure_skills",
    "_configure_tools",
    "_configure_tools_advanced_keys",
    "_configure_tools_docker",
    "_configure_tools_execution",
    "_configure_tools_runtime_mode",
    "_configure_tools_web_search",
    "_describe_skill_setup_hint",
    "_detect_skill_auth_hint",
    "_extract_skill_candidate_subdirs",
    "_extract_skill_capability_summary",
    "_format_candidate_label",
    "_inject_configured_skill_env",
    "_inject_skill_persona",
    "_install_step_hint",
    "_is_interactive_tty",
    "_is_secret_env_name",
    "_load_skill_agents_snippet",
    "_load_skill_persona_snippet",
    "_normalize_candidate_rows",
    "_preview_snippet",
    "_print_manual_install_plan",
    "_prompt_skill_candidate_subdir",
    "_resolve_skill_install_target_dir",
    "_set_install_settings",
    "_set_kabot_freedom_mode",
    "_state_label",
    "_token_mode_label",
    "_wizard_install_external_skill",
    "bind_tools_gateway_skills_sections",
    "console",
    "skills_checkbox",
]

def _configure_tools(self):
    ClackUI.section_start("Tools & Sandbox")

    # Mark section as in progress
    self._save_setup_state("tools", completed=False, in_progress=True)

    while True:
        search_cfg = self.config.tools.web.search
        docker_cfg = self.config.tools.exec.docker
        choices = [
            questionary.Choice(
                f"Web Search (provider={search_cfg.provider}, brave_key={_state_label(search_cfg.api_key)}, max={search_cfg.max_results})",
                value="web",
            ),
            questionary.Choice(
                f"Execution Policy (freedom={_bool_label(self.config.tools.exec.auto_approve)}, restrict_ws={_bool_label(self.config.tools.restrict_to_workspace)}, timeout={self.config.tools.exec.timeout}s)",
                value="execution",
            ),
            questionary.Choice(
                f"Docker Sandbox ({_bool_label(docker_cfg.enabled)})",
                value="docker",
            ),
            questionary.Choice(
                f"Advanced API Keys (firecrawl={_state_label(self.config.tools.web.fetch.firecrawl_api_key)}, perplexity={_state_label(search_cfg.perplexity_api_key)}, kimi={_state_label(search_cfg.kimi_api_key)}, xai={_state_label(search_cfg.xai_api_key)})",
                value="advanced",
            ),
            questionary.Choice(
                f"Runtime Token Mode ({_token_mode_label(self.config.runtime.performance.token_mode)})",
                value="runtime_mode",
            ),
            questionary.Choice("Back", value="back"),
        ]

        choice = ClackUI.clack_select("Tools & Sandbox menu", choices=choices)
        if choice in {None, "back"}:
            break
        if choice == "web":
            _configure_tools_web_search(self)
        elif choice == "execution":
            _configure_tools_execution(self)
        elif choice == "docker":
            _configure_tools_docker(self)
        elif choice == "advanced":
            _configure_tools_advanced_keys(self)
        elif choice == "runtime_mode":
            _configure_tools_runtime_mode(self)

    # Summary
    console.print("|")
    adv_tools = []
    if self.config.tools.web.fetch.firecrawl_api_key:
        adv_tools.append("FireCrawl")
    if self.config.tools.web.search.perplexity_api_key:
        adv_tools.append("Perplexity")
    if self.config.tools.web.search.kimi_api_key:
        adv_tools.append("Kimi")
    if self.config.tools.web.search.xai_api_key:
        adv_tools.append("Grok")
    if adv_tools:
        console.print(f"|  [bold green]Military-grade tools active: {', '.join(adv_tools)}[/bold green]")
    else:
        console.print("|  [dim]Standard mode (all tools work with defaults)[/dim]")
    console.print(
        f"|  [dim]Token mode: {_token_mode_label(self.config.runtime.performance.token_mode)}[/dim]"
    )

    # Mark as completed and save configuration
    docker_enabled = bool(self.config.tools.exec.docker.enabled)
    freedom_mode = bool(self.config.tools.exec.auto_approve)
    self._save_setup_state("tools", completed=True,
                         web_search_enabled=bool(self.config.tools.web.search.api_key),
                         docker_enabled=docker_enabled,
                         restrict_to_workspace=self.config.tools.restrict_to_workspace,
                         freedom_mode=freedom_mode,
                         token_mode=str(self.config.runtime.performance.token_mode or "boros"))

    ClackUI.section_end()

def _configure_tools_runtime_mode(self) -> None:
    current = str(self.config.runtime.performance.token_mode or "boros").strip().lower()
    if current not in {"boros", "hemat"}:
        current = "boros"

    choice = ClackUI.clack_select(
        "Select runtime token mode",
        choices=[
            questionary.Choice(
                "BOROS (default) - more context, richer responses, higher token usage",
                value="boros",
            ),
            questionary.Choice(
                "HEMAT - tighter context + stricter truncation for lower token usage",
                value="hemat",
            ),
            questionary.Choice("Back", value="back"),
        ],
        default=current,
    )
    if choice in {None, "back"}:
        return

    self.config.runtime.performance.token_mode = "hemat" if choice == "hemat" else "boros"
    console.print(
        f"|  [green]OK Runtime token mode set to {_token_mode_label(self.config.runtime.performance.token_mode)}[/green]"
    )

def _configure_tools_web_search(self) -> None:
    while True:
        cfg = self.config.tools.web.search
        choice = ClackUI.clack_select(
            "Web Search",
            choices=[
                questionary.Choice(f"Brave Search API Key ({_state_label(cfg.api_key)})", value="brave_key"),
                questionary.Choice(f"Max Search Results ({cfg.max_results})", value="max_results"),
                questionary.Choice(f"Default Provider ({cfg.provider})", value="provider"),
                questionary.Choice("Back", value="back"),
            ],
        )
        if choice in {None, "back"}:
            return

        if choice == "brave_key":
            value = Prompt.ask("|  Brave Search API Key", default=cfg.api_key or "").strip()
            if value.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            cfg.api_key = value
            console.print("|  [green]OK Brave key updated[/green]")
            continue

        if choice == "max_results":
            raw = Prompt.ask("|  Max Search Results", default=str(cfg.max_results)).strip()
            if raw.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            try:
                parsed = int(raw)
                if parsed <= 0:
                    raise ValueError("must be > 0")
                cfg.max_results = parsed
                console.print(f"|  [green]OK Max Search Results set to {parsed}[/green]")
            except (TypeError, ValueError):
                console.print("|  [yellow]Invalid number, keeping previous value[/yellow]")
            continue

        provider = ClackUI.clack_select(
            "Default search provider",
            choices=[
                questionary.Choice("Brave", value="brave"),
                questionary.Choice("Perplexity", value="perplexity"),
                questionary.Choice("Kimi", value="kimi"),
                questionary.Choice("Grok (xAI)", value="grok"),
                questionary.Choice("Back", value="back"),
            ],
            default=cfg.provider if cfg.provider in {"brave", "perplexity", "kimi", "grok"} else "brave",
        )
        if provider in {None, "back"}:
            continue

        if provider == "perplexity" and not str(cfg.perplexity_api_key or "").strip():
            console.print("|  [yellow]Perplexity key is empty; requests may fail until key is set.[/yellow]")
        elif provider == "kimi" and not str(cfg.kimi_api_key or "").strip():
            console.print("|  [yellow]Kimi key is empty; requests may fail until key is set.[/yellow]")
        elif provider == "grok" and not str(cfg.xai_api_key or "").strip():
            console.print("|  [yellow]xAI key is empty; requests may fail until key is set.[/yellow]")

        cfg.provider = provider
        console.print(f"|  [green]OK Default provider set to {provider}[/green]")

def _configure_tools_execution(self) -> None:
    while True:
        choice = ClackUI.clack_select(
            "Execution Policy",
            choices=[
                questionary.Choice(
                    f"Security preset ({self.config.tools.exec.policy_preset})",
                    value="policy_preset",
                ),
                questionary.Choice(
                    f"Enable Kabot freedom mode [Trusted environment only] ({_bool_label(self.config.tools.exec.auto_approve)})",
                    value="freedom",
                ),
                questionary.Choice(
                    f"Restrict file-system usage to workspace ({_bool_label(self.config.tools.restrict_to_workspace)})",
                    value="restrict_workspace",
                ),
                questionary.Choice(f"Command Timeout ({self.config.tools.exec.timeout}s)", value="timeout"),
                questionary.Choice("Back", value="back"),
            ],
        )
        if choice in {None, "back"}:
            return

        if choice == "policy_preset":
            preset = ClackUI.clack_select(
                "Select security preset",
                choices=[
                    questionary.Choice("strict (recommended)", value="strict"),
                    questionary.Choice("balanced", value="balanced"),
                    questionary.Choice("compat", value="compat"),
                    questionary.Choice("Back", value="back"),
                ],
                default=self.config.tools.exec.policy_preset
                if self.config.tools.exec.policy_preset in {"strict", "balanced", "compat"}
                else "strict",
            )
            if preset in {None, "back"}:
                continue
            self.config.tools.exec.policy_preset = preset
            console.print(f"|  [green]OK Security preset set to {preset}[/green]")
            continue

        if choice == "freedom":
            freedom_mode = Confirm.ask(
                "|  Enable Kabot freedom mode [Trusted environment only]",
                default=bool(self.config.tools.exec.auto_approve),
            )
            self._set_kabot_freedom_mode(freedom_mode)
            self.config.tools.exec.auto_approve = freedom_mode
            continue

        if choice == "restrict_workspace":
            self.config.tools.restrict_to_workspace = Confirm.ask(
                "|  Restrict File System usage to workspace",
                default=self.config.tools.restrict_to_workspace,
            )
            continue

        raw = Prompt.ask("|  Command Timeout (s)", default=str(self.config.tools.exec.timeout)).strip()
        if raw.lower() == "back":
            console.print("|  [yellow]Cancelled[/yellow]")
            continue
        try:
            timeout = int(raw)
            if timeout <= 0:
                raise ValueError("must be > 0")
            self.config.tools.exec.timeout = timeout
            console.print(f"|  [green]OK Command timeout set to {timeout}s[/green]")
        except (TypeError, ValueError):
            console.print("|  [yellow]Invalid timeout, keeping previous value[/yellow]")

def _configure_tools_docker(self) -> None:
    cfg = self.config.tools.exec.docker
    while True:
        choice = ClackUI.clack_select(
            "Docker Sandbox",
            choices=[
                questionary.Choice(f"Enable Docker Sandbox ({_bool_label(cfg.enabled)})", value="enabled"),
                questionary.Choice(f"Docker Image ({cfg.image})", value="image"),
                questionary.Choice(f"Memory Limit ({cfg.memory_limit})", value="memory_limit"),
                questionary.Choice(f"CPU Limit ({cfg.cpu_limit})", value="cpu_limit"),
                questionary.Choice(f"Disable Network ({_bool_label(cfg.network_disabled)})", value="network_disabled"),
                questionary.Choice("Back", value="back"),
            ],
        )
        if choice in {None, "back"}:
            return

        if choice == "enabled":
            cfg.enabled = Confirm.ask("|  Enable Docker Sandbox", default=cfg.enabled)
            continue
        if choice == "image":
            value = Prompt.ask("|  Docker Image", default=cfg.image).strip()
            if value.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            if value:
                cfg.image = value
            continue
        if choice == "memory_limit":
            value = Prompt.ask("|  Memory Limit", default=cfg.memory_limit).strip()
            if value.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            if value:
                cfg.memory_limit = value
            continue
        if choice == "cpu_limit":
            raw = Prompt.ask("|  CPU Limit", default=str(cfg.cpu_limit)).strip()
            if raw.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            try:
                cpu = float(raw)
                if cpu <= 0:
                    raise ValueError("must be > 0")
                cfg.cpu_limit = cpu
            except (TypeError, ValueError):
                console.print("|  [yellow]Invalid CPU limit, keeping previous value[/yellow]")
            continue
        cfg.network_disabled = Confirm.ask("|  Disable Network in Sandbox", default=cfg.network_disabled)

def _configure_tools_advanced_keys(self) -> None:
    while True:
        search_cfg = self.config.tools.web.search
        fetch_cfg = self.config.tools.web.fetch
        choice = ClackUI.clack_select(
            "Advanced API Keys",
            choices=[
                questionary.Choice(
                    f"FireCrawl API Key ({_state_label(fetch_cfg.firecrawl_api_key)})",
                    value="firecrawl_key",
                ),
                questionary.Choice(
                    f"Perplexity API Key ({_state_label(search_cfg.perplexity_api_key)})",
                    value="perplexity_key",
                ),
                questionary.Choice(
                    f"Kimi API Key ({_state_label(search_cfg.kimi_api_key)})",
                    value="kimi_key",
                ),
                questionary.Choice(
                    f"xAI API Key ({_state_label(search_cfg.xai_api_key)})",
                    value="xai_key",
                ),
                questionary.Choice("Back", value="back"),
            ],
        )
        if choice in {None, "back"}:
            return

        if choice == "firecrawl_key":
            value = Prompt.ask(
                "|  FireCrawl API Key (JS rendering)",
                default=fetch_cfg.firecrawl_api_key or "",
            ).strip()
            if value.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            fetch_cfg.firecrawl_api_key = value
            continue

        if choice == "perplexity_key":
            value = Prompt.ask(
                "|  Perplexity API Key (AI search)",
                default=search_cfg.perplexity_api_key or "",
            ).strip()
            if value.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            search_cfg.perplexity_api_key = value
            if value:
                search_cfg.provider = "perplexity"
            elif search_cfg.provider == "perplexity":
                search_cfg.provider = _best_search_provider_from_keys(self)
            continue

        if choice == "kimi_key":
            value = Prompt.ask(
                "|  Kimi API Key (Moonshot web search)",
                default=search_cfg.kimi_api_key or "",
            ).strip()
            if value.lower() == "back":
                console.print("|  [yellow]Cancelled[/yellow]")
                continue
            search_cfg.kimi_api_key = value
            if value and not str(search_cfg.perplexity_api_key or "").strip():
                search_cfg.provider = "kimi"
            elif search_cfg.provider == "kimi":
                search_cfg.provider = _best_search_provider_from_keys(self)
            continue

        value = Prompt.ask(
            "|  xAI API Key (Grok search)",
            default=search_cfg.xai_api_key or "",
        ).strip()
        if value.lower() == "back":
            console.print("|  [yellow]Cancelled[/yellow]")
            continue
        search_cfg.xai_api_key = value
        if (
            value
            and not str(search_cfg.perplexity_api_key or "").strip()
            and not str(search_cfg.kimi_api_key or "").strip()
        ):
            search_cfg.provider = "grok"
        elif search_cfg.provider == "grok":
            search_cfg.provider = _best_search_provider_from_keys(self)

def _set_kabot_freedom_mode(self, enabled: bool) -> None:
    """Apply trusted-mode defaults for maximum tool flexibility."""
    if enabled:
        self.config.tools.exec.auto_approve = True
        self.config.tools.exec.policy_preset = "compat"
        self.config.tools.restrict_to_workspace = False
        self.config.integrations.http_guard.enabled = False
        self.config.integrations.http_guard.block_private_networks = False
        self.config.integrations.http_guard.allow_hosts = []
        self.config.integrations.http_guard.deny_hosts = []
        return

    self.config.tools.exec.auto_approve = False
    if self.config.tools.exec.policy_preset == "compat":
        self.config.tools.exec.policy_preset = "strict"
    self.config.integrations.http_guard.enabled = True
    self.config.integrations.http_guard.block_private_networks = True
    self.config.integrations.http_guard.allow_hosts = []
    self.config.integrations.http_guard.deny_hosts = [
        "localhost",
        "127.0.0.1",
        "169.254.169.254",
        "metadata.google.internal",
    ]

def _configure_gateway(self):
    ClackUI.section_start("Gateway")

    # Mark section as in progress
    self._save_setup_state("gateway", completed=False, in_progress=True)

    # Bind Mode
    modes = [
        questionary.Choice("Loopback (Localhost only) [Secure]", value="loopback"),
        questionary.Choice("Local Network (LAN)", value="local"),
        questionary.Choice("Public (0.0.0.0) [Unsafe without Auth]", value="public"),
        questionary.Choice("Tailscale (Private VPN)", value="tailscale"),
    ]
    bind_val = ClackUI.clack_select("Bind Mode", choices=modes, default=self.config.gateway.bind_mode)
    if bind_val is None:
        ClackUI.section_end()
        return
    if bind_val:
        self.config.gateway.bind_mode = bind_val
        if bind_val == "loopback":
            self.config.gateway.host = "127.0.0.1"
        elif bind_val == "local":
            self.config.gateway.host = "0.0.0.0" # Simplification, or prompt for specific IP usually 0.0.0.0 is fine for LAN
        elif bind_val == "public":
            self.config.gateway.host = "0.0.0.0"
        elif bind_val == "tailscale":
            self.config.gateway.host = "127.0.0.1"
            self.config.gateway.tailscale = True

    port_input = Prompt.ask("|  Port", default=str(self.config.gateway.port))
    try:
        self.config.gateway.port = int(port_input)
    except (TypeError, ValueError):
        console.print("|  [yellow]Invalid port, keeping previous value[/yellow]")

    # Auth Config
    auth_mode = ClackUI.clack_select("Authentication", choices=[
        questionary.Choice("Token (Bearer)", value="token"),
        questionary.Choice("None (Testing only)", value="none"),
    ], default="token" if self.config.gateway.auth_token else "none")
    if auth_mode is None:
        ClackUI.section_end()
        return

    auth_configured = False
    if auth_mode == "token":
        import secrets
        current = self.config.gateway.auth_token
        default_token = current if current else secrets.token_hex(16)
        token = Prompt.ask("|  Auth Token", default=default_token)
        self.config.gateway.auth_token = token
        auth_configured = bool(token)
    else:
        self.config.gateway.auth_token = ""

    # Tailscale explicit toggle if not selected in bind mode
    if bind_val != "tailscale":
         self.config.gateway.tailscale = Confirm.ask("|  Enable Tailscale Funnel", default=self.config.gateway.tailscale)

    # Optional HSTS header for HTTPS deployments
    hsts_cfg = self.config.gateway.http.security_headers
    hsts_cfg.strict_transport_security = Confirm.ask(
        "|  Enable Strict-Transport-Security header (HTTPS only)",
        default=hsts_cfg.strict_transport_security,
    )
    if hsts_cfg.strict_transport_security:
        header_value = Prompt.ask(
            "|  HSTS value",
            default=hsts_cfg.strict_transport_security_value,
        ).strip()
        if header_value:
            hsts_cfg.strict_transport_security_value = header_value

    # Mark as completed and save configuration
    self._save_setup_state("gateway", completed=True,
                         bind_mode=bind_val,
                         port=self.config.gateway.port,
                         auth_configured=auth_configured,
                         tailscale_enabled=self.config.gateway.tailscale,
                         hsts_enabled=hsts_cfg.strict_transport_security)

    ClackUI.section_end()

def _configure_skills(self):
    ClackUI.section_start("Skills")
    console.print("|  [dim]This section configures skills and prepares dependency install plans.[/dim]")
    console.print("|  [dim]Native Google setup lives in the separate Google Suite menu.[/dim]")
    console.print("|  [dim]Any npm/pnpm/bun choice here only affects manual install hints for node-based skills.[/dim]")

    # Mark section as in progress
    self._save_setup_state("skills", completed=False, in_progress=True)

    injected_env_count = self._inject_configured_skill_env()
    if injected_env_count > 0:
        console.print(f"|  [dim]Loaded {injected_env_count} configured skill env var(s)[/dim]")

    from kabot.agent.skills import SkillsLoader
    loader = SkillsLoader(self.config.workspace_path, skills_config=self.config.skills)

    # 1. Load all skills with detailed status
    all_skills = loader.list_skills(filter_unavailable=False)

    eligible = [s for s in all_skills if s["eligible"]]
    blocked = [s for s in all_skills if s.get("blocked_by_allowlist")]
    disabled = [s for s in all_skills if s.get("disabled")]
    unsupported = [s for s in all_skills if s["missing"]["os"] and not s.get("blocked_by_allowlist")]
    missing_reqs = [
        s
        for s in all_skills
        if (
            not s["eligible"]
            and not s["missing"]["os"]
            and not s.get("blocked_by_allowlist")
            and not s.get("disabled")
        )
    ]

    # 2. Status Board
    console.print("|")
    console.print("*  Skills status -------------+")
    console.print("|                             |")
    console.print(f"|  Eligible: {len(eligible):<17}|")
    console.print(f"|  Missing requirements: {len(missing_reqs):<5}|")
    console.print(f"|  Unsupported on this OS: {len(unsupported):<3}|")
    console.print(f"|  Blocked by allowlist: {len(blocked):<5}|")
    console.print(f"|  Disabled in config: {len(disabled):<5}|")
    console.print("|                             |")
    console.print("+-----------------------------+")
    console.print("|")

    configured_skills = []
    installed_skills = []

    # 3. Configure/Install Prompt
    if not Confirm.ask("*  Configure skills now (recommended)", default=True):
        # Mark as completed even if skipped
        self._save_setup_state("skills", completed=True,
                             configured_skills=configured_skills,
                             installed_skills=installed_skills,
                             skipped=True)
        ClackUI.section_end()
        return

    if _is_interactive_tty() and Confirm.ask("*  Install external skill from git now", default=False):
        while True:
            installed_result = _wizard_install_external_skill(self)
            if installed_result:
                skill_name = str(installed_result.get("skill_name") or "").strip()
                skill_key = str(installed_result.get("skill_key") or "").strip()
                if skill_name and skill_name not in installed_skills:
                    installed_skills.append(skill_name)
                if skill_key and skill_key not in configured_skills:
                    configured_skills.append(skill_key)
            if not Confirm.ask("*  Install another external skill from git", default=False):
                break
            console.print("|")

        # Refresh skill snapshot after potential installs.
        all_skills = loader.list_skills(filter_unavailable=False)
        eligible = [s for s in all_skills if s["eligible"]]
        blocked = [s for s in all_skills if s.get("blocked_by_allowlist")]
        disabled = [s for s in all_skills if s.get("disabled")]
        unsupported = [s for s in all_skills if s["missing"]["os"] and not s.get("blocked_by_allowlist")]
        missing_reqs = [
            s
            for s in all_skills
            if (
                not s["eligible"]
                and not s["missing"]["os"]
                and not s.get("blocked_by_allowlist")
                and not s.get("disabled")
            )
        ]
        console.print(
            f"|  [dim]Skill inventory refreshed: eligible={len(eligible)}, missing={len(missing_reqs)}, "
            f"unsupported={len(unsupported)}, blocked={len(blocked)}, disabled={len(disabled)}[/dim]"
        )

    # 4. Installation Flow (manual plan only; no command execution)
    installable = [s for s in missing_reqs if s["missing"]["bins"] or s.get("install")]
    install_settings = resolve_install_settings(self.config.skills)
    # Persist canonical install settings so config remains stable.
    self.config.skills = _set_install_settings(
        self.config.skills,
        mode=str(install_settings.get("mode") or "manual"),
        node_manager=str(install_settings.get("node_manager") or "npm"),
        prefer_brew=bool(install_settings.get("prefer_brew", True)),
    )
    install_settings = resolve_install_settings(self.config.skills)

    if installable:
        options = [
            {
                "value": "skip",
                "label": "Skip for now",
                "hint": "Continue without dependency planning",
            }
        ]
        for skill in installable:
            options.append(
                {
                    "value": skill["name"],
                    "label": str(skill["name"]),
                    "hint": _describe_skill_setup_hint(skill, loader),
                }
            )

        console.print("|")
        console.print("*  Prepare skill dependency setup plans")
        selected_names = skills_checkbox("Select skills to prepare install plan for", options=options)
        selected_install_names = [name for name in selected_names if name not in {"skip", "back"}]

        selected_install_skills = [
            skill for skill in installable if skill.get("name") in selected_install_names
        ]

        needs_node_manager = any(
            any(str(spec.get("kind") or "").strip().lower() == "node" for spec in (skill.get("install") or []))
            for skill in selected_install_skills
        )
        if needs_node_manager:
            node_manager = ClackUI.clack_select(
                "Preferred node manager for manual skill install plans",
                choices=[
                    questionary.Choice("npm", value="npm"),
                    questionary.Choice("pnpm", value="pnpm"),
                    questionary.Choice("yarn", value="yarn"),
                    questionary.Choice("bun", value="bun"),
                    questionary.Choice("Back", value="back"),
                ],
                default=str(install_settings.get("node_manager") or "npm"),
            )
            if node_manager and node_manager != "back":
                self.config.skills = _set_install_settings(self.config.skills, node_manager=node_manager)

        if selected_install_skills:
            console.print("|  [dim]Manual install planning mode active (no commands will be executed).[/dim]")
            for skill in selected_install_skills:
                _print_manual_install_plan(skill)
                if skill.get("name") not in installed_skills:
                    installed_skills.append(str(skill.get("name")))
                console.print(f"|  [dim]Finished plan for {skill.get('name')}[/dim]")

    # 5. Environment Variable Configuration (selected skills only)
    console.print("|")

    # Filter for skills that need keys.
    needs_env = []
    for s in all_skills:
        if s['missing']['env']:
            needs_env.append(s)

    if needs_env:
        env_options = [
            {
                "value": "skip",
                "label": "Skip key setup for now",
                "hint": "You can configure env keys later",
            }
        ]
        for s in needs_env:
            missing_env = ", ".join(s.get("missing", {}).get("env", []))
            label = s["name"]
            env_options.append(
                {
                    "value": s["name"],
                    "label": label,
                    "hint": f"needs env: {missing_env}" if missing_env else "needs env",
                }
            )

        console.print("*  Configure skill environment variables")
        selected_env_skill_names = skills_checkbox(
            "Select skills to configure environment variables for",
            options=env_options,
        ) or []

        if any(name in {"skip", "back"} for name in selected_env_skill_names) or not selected_env_skill_names:
            console.print("|  [dim]Skipped skill environment variable setup for now[/dim]")
        else:
            selected_skills = [s for s in needs_env if s["name"] in selected_env_skill_names]
            selected_by_name = {s["name"]: s for s in selected_skills}
            env_to_skills: dict[str, list[str]] = {}
            for skill in selected_skills:
                missing_envs = [
                    str(env_key).strip()
                    for env_key in (skill.get("missing", {}).get("env", []) or [])
                    if str(env_key).strip()
                ]
                if not missing_envs:
                    primary_env = str(skill.get("primaryEnv") or "").strip()
                    if primary_env:
                        missing_envs = [primary_env]
                for env_key in missing_envs:
                    env_to_skills.setdefault(env_key, [])
                    if skill["name"] not in env_to_skills[env_key]:
                        env_to_skills[env_key].append(skill["name"])

            for env_key, skill_names in env_to_skills.items():
                label_skills = ", ".join(skill_names)
                if not Confirm.ask(f"*  Set {env_key} for [cyan]{label_skills}[/cyan]", default=True):
                    console.print("|")
                    continue

                current_val = os.environ.get(env_key)
                val = Prompt.ask(f"|  Enter {env_key}", default=current_val or "", password=True)
                if str(val).strip().lower() == "back":
                    console.print("|  [yellow]Cancelled[/yellow]")
                    console.print("|")
                    continue

                if val:
                    for skill_name in skill_names:
                        skill_obj = selected_by_name.get(skill_name, {})
                        skill_key = str(skill_obj.get("skill_key") or skill_name)
                        self.config.skills = set_skill_entry_env(self.config.skills, skill_key, env_key, val)
                        if skill_name not in configured_skills:
                            configured_skills.append(skill_name)
                    os.environ[env_key] = val
                    console.print("|  [green]OK Saved[/green]")
                console.print("|")

    # Install built-in skills after configuration
    console.print("|")
    builtin_installed = self._install_builtin_skills_with_progress()

    # Mark as completed and save configuration
    self._save_setup_state("skills", completed=True,
                         configured_skills=configured_skills,
                         installed_skills=installed_skills,
                         builtin_skills_installed=builtin_installed,
                         eligible_count=len(eligible),
                         missing_reqs_count=len(missing_reqs))

    ClackUI.section_end()

def _inject_configured_skill_env(self) -> int:
    injected = 0
    configured_skills = getattr(self.config, "skills", {}) or {}
    for _, key, value in iter_skill_env_pairs(configured_skills):
        if key not in os.environ:
            os.environ[key] = str(value)
            injected += 1
    return injected

def bind_tools_gateway_skills_sections(cls):
    cls._configure_tools = _configure_tools
    cls._configure_tools_runtime_mode = _configure_tools_runtime_mode
    cls._set_kabot_freedom_mode = _set_kabot_freedom_mode
    cls._configure_gateway = _configure_gateway
    cls._configure_skills = _configure_skills
    cls._inject_configured_skill_env = _inject_configured_skill_env
    return cls
