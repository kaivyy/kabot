"""SetupWizard section methods: channels."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt

from kabot.cli.fleet_templates import FLEET_TEMPLATES, get_template_roles
from kabot.cli.wizard.ui import ClackUI
from kabot.config.schema import AgentBinding, AgentBindingMatch, AgentConfig, ChannelInstance
from kabot.utils.workspace_templates import ensure_workspace_templates

console = Console()

def _discord_intents_default_value(self, current: Any) -> str:
    if isinstance(current, int):
        return str(current)
    if isinstance(current, list):
        values = [str(item) for item in current if isinstance(item, int)]
        return ",".join(values) if values else "37377"
    return "37377"

def _parse_discord_intents(self, raw_value: str) -> int | None:
    cleaned = (raw_value or "").strip()
    if not cleaned:
        return None
    try:
        if "," not in cleaned:
            return int(cleaned, 0)
        value = 0
        for segment in cleaned.split(","):
            bit = segment.strip()
            if not bit:
                continue
            value |= int(bit, 0)
        return value
    except ValueError:
        return None

def _parse_allow_from_values(raw_value: str) -> list[str]:
    """Parse comma/newline separated allowFrom values with dedupe."""
    seen: set[str] = set()
    parsed: list[str] = []
    for part in (raw_value or "").replace("\n", ",").split(","):
        item = part.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        parsed.append(item)
    return parsed

def _prompt_secret_value(self, label: str, current: str | None = None) -> str:
    """Prompt secret-like value without echoing current value as default."""
    if current:
        console.print(f"|  [dim]{label}: leave empty to keep existing value[/dim]")
    value = Prompt.ask(label, default="").strip()
    if not value and current:
        return current
    return value

def _prompt_allow_from_list(self, label: str, current: Optional[list[str]] = None) -> list[str]:
    """Prompt allowFrom list for channel security."""
    existing = [str(item).strip() for item in (current or []) if str(item).strip()]
    strict_preset = str(getattr(self.config.tools.exec, "policy_preset", "balanced") or "balanced").strip().lower() == "strict"
    console.print(f"|  [dim]{label} (comma separated, empty = allow all)[/dim]")
    if existing:
        console.print(f"|  [dim]Current allowFrom entries: {len(existing)}[/dim]")
        console.print("|  [dim]Leave empty to keep current allowFrom[/dim]")
    raw = Prompt.ask("|  allowFrom", default="").strip()
    if not raw:
        if strict_preset and not existing:
            console.print(
                "|  [yellow]Strict preset active: empty allowFrom means deny-all until you add at least one user.[/yellow]"
            )
        return existing
    parsed = _parse_allow_from_values(raw)
    if strict_preset and not parsed:
        console.print(
            "|  [yellow]Strict preset active: empty allowFrom means deny-all until you add at least one user.[/yellow]"
        )
    return parsed

def _pick_agent_model_override(self) -> str | None:
    """Optional per-agent model picker without changing global default model."""
    choice = ClackUI.clack_select(
        "Set model for this agent",
        choices=[
            questionary.Choice("Pick from configured provider models (Recommended)", value="browse"),
            questionary.Choice("Enter model ID manually", value="manual"),
            questionary.Choice("Use global default model", value="skip"),
            questionary.Choice("Back", value="back"),
        ],
        default="browse",
    )
    if choice in (None, "skip", "back"):
        return None

    if choice == "manual":
        raw = Prompt.ask("|  Agent Model", default="").strip()
        return raw or None

    allowed_provider_ids: list[str] | None = None
    if hasattr(self, "_providers_with_saved_credentials"):
        allowed_provider_ids = self._providers_with_saved_credentials()
    selected = self._model_browser(
        provider_id=None,
        apply_selection=False,
        allowed_provider_ids=allowed_provider_ids or None,
    )
    if selected:
        console.print(f"|  [green]OK Agent model selected: {selected}[/green]")
    else:
        console.print("|  [yellow]No model selected; using global default model[/yellow]")
    return selected

def _find_channel_default_binding(self, channel_type: str) -> AgentBinding | None:
    """Find wizard-managed default binding for a legacy channel."""
    for binding in self.config.agents.bindings:
        match = binding.match
        if (
            (match.channel or "").strip().lower() == channel_type
            and (match.account_id or "").strip() == "*"
            and match.peer is None
            and match.guild_id is None
            and match.team_id is None
        ):
            return binding
    return None

def _upsert_channel_default_binding(self, channel_type: str, agent_id: str) -> None:
    """Create or update channel-wide binding for legacy single-instance channels."""
    existing = self._find_channel_default_binding(channel_type)
    if existing:
        existing.agent_id = agent_id
        return
    self.config.agents.bindings.append(
        AgentBinding(
            agent_id=agent_id,
            match=AgentBindingMatch(channel=channel_type, account_id="*"),
        )
    )

def _remove_channel_default_binding(self, channel_type: str) -> None:
    """Remove wizard-managed default binding for a legacy channel."""
    self.config.agents.bindings = [
        binding
        for binding in self.config.agents.bindings
        if not (
            (binding.match.channel or "").strip().lower() == channel_type
            and (binding.match.account_id or "").strip() == "*"
            and binding.match.peer is None
            and binding.match.guild_id is None
            and binding.match.team_id is None
        )
    ]

def _configure_legacy_channel_ai_binding(self, channel_type: str) -> None:
    """Optionally bind a legacy channel to a dedicated agent/model."""
    if not Confirm.ask(
        f"|  Configure AI routing for '{channel_type}' channel (agent/model)",
        default=True,
    ):
        return

    default_agent_id = f"{channel_type}_main"
    agent_binding, auto_create_agent, model_override = self._prompt_agent_binding(default_agent_id)

    if auto_create_agent and agent_binding:
        resolved_agent = self._ensure_agent_exists(agent_binding, model_override=model_override)
        self._upsert_channel_default_binding(channel_type, resolved_agent)
        console.print(
            f"|  [green]OK[/green] Channel '{channel_type}' bound to dedicated agent '{resolved_agent}'"
        )
        return

    if agent_binding:
        resolved_agent = self._ensure_agent_exists(agent_binding)
        if Confirm.ask("|  Change model for this bound agent now", default=False):
            selected_model = self._pick_agent_model_override()
            if selected_model:
                self._ensure_agent_exists(resolved_agent, model_override=selected_model)
        self._upsert_channel_default_binding(channel_type, resolved_agent)
        console.print(f"|  [green]OK[/green] Channel '{channel_type}' bound to agent '{resolved_agent}'")
        return

    # Explicitly keep shared default route
    self._remove_channel_default_binding(channel_type)
    console.print(f"|  [dim]Channel '{channel_type}' uses shared default agent/model[/dim]")

def _instance_id_exists(self, instance_id: str) -> bool:
    return any(inst.id == instance_id for inst in self.config.channels.instances)

def _next_available_instance_id(self, preferred_id: str) -> str:
    base = (preferred_id or "").strip().replace(" ", "_")
    if not base:
        base = "bot"
    if not self._instance_id_exists(base):
        return base
    i = 2
    while True:
        candidate = f"{base}_{i}"
        if not self._instance_id_exists(candidate):
            return candidate
        i += 1

def _ensure_agent_exists(self, agent_id: str, model_override: str | None = None) -> str:
    clean_id = (agent_id or "").strip().replace(" ", "_") or "main"
    existing = next((a for a in self.config.agents.agents if a.id == clean_id), None)
    if existing:
        if existing.workspace:
            ensure_workspace_templates(Path(existing.workspace).expanduser())
        if model_override:
            existing.model = model_override
        return clean_id

    workspace_path = Path.home() / ".kabot" / f"workspace-{clean_id}"
    ensure_workspace_templates(workspace_path)
    self.config.agents.agents.append(
        AgentConfig(
            id=clean_id,
            name=clean_id.replace("_", " ").title(),
            model=model_override or None,
            workspace=str(workspace_path),
            default=(len(self.config.agents.agents) == 0),
        )
    )
    return clean_id

def _add_channel_instance_record(
    self,
    *,
    instance_id: str,
    channel_type: str,
    config_dict: dict[str, Any],
    agent_binding: str | None = None,
    auto_create_agent: bool = False,
    model_override: str | None = None,
) -> ChannelInstance:
    final_id = self._next_available_instance_id(instance_id)
    final_binding = agent_binding
    if auto_create_agent:
        final_binding = self._ensure_agent_exists(final_binding or final_id, model_override=model_override)

    instance = ChannelInstance(
        id=final_id,
        type=channel_type,
        enabled=True,
        config=config_dict,
        agent_binding=final_binding,
    )
    self.config.channels.instances.append(instance)
    return instance

def _prompt_instance_config(self, channel_type: str) -> dict[str, Any] | None:
    if channel_type == "telegram":
        token = Prompt.ask("|  Bot Token")
        if not token:
            return None
        allow_from = self._prompt_allow_from_list("Allowed users for this Telegram bot")
        return {"token": token, "allow_from": allow_from}

    if channel_type == "discord":
        token = Prompt.ask("|  Bot Token")
        if not token:
            return None
        allow_from = self._prompt_allow_from_list("Allowed users for this Discord bot")
        return {"token": token, "allow_from": allow_from}

    if channel_type == "whatsapp":
        bridge_url = Prompt.ask("|  Bridge URL", default="ws://localhost:3001")
        allow_from = self._prompt_allow_from_list("Allowed WhatsApp numbers for this bot")
        return {"bridge_url": bridge_url, "allow_from": allow_from}

    if channel_type == "slack":
        bot_token = Prompt.ask("|  Bot Token (xoxb-...)")
        app_token = Prompt.ask("|  App Token (xapp-...)")
        if not bot_token or not app_token:
            return None
        return {"bot_token": bot_token, "app_token": app_token}

    if channel_type in {
        "signal",
        "matrix",
        "teams",
        "google_chat",
        "mattermost",
        "webex",
        "line",
    }:
        default_url = {
            "signal": "ws://localhost:3011",
            "matrix": "ws://localhost:3012",
            "teams": "ws://localhost:3013",
            "google_chat": "ws://localhost:3014",
            "mattermost": "ws://localhost:3015",
            "webex": "ws://localhost:3016",
            "line": "ws://localhost:3017",
        }[channel_type]
        bridge_url = Prompt.ask("|  Bridge URL", default=default_url).strip() or default_url
        allow_from = self._prompt_allow_from_list(
            f"Allowed users for this {channel_type} bot"
        )
        return {"bridge_url": bridge_url, "allow_from": allow_from}

    return None

def _prompt_agent_binding(self, default_agent_id: str) -> tuple[str | None, bool, str | None]:
    if not self.config.agents.agents:
        if Confirm.ask("|  Auto-create dedicated agent for this bot", default=True):
            model_override = self._pick_agent_model_override()
            return default_agent_id, True, model_override or None
        return None, False, None

    if not Confirm.ask("|  Bind this bot to a specific agent", default=False):
        return None, False, None

    choices = [
        questionary.Choice("No binding (shared default)", value="__none__"),
        questionary.Choice("Create new agent", value="__create__"),
    ]
    choices.extend(questionary.Choice(agent.id, value=agent.id) for agent in self.config.agents.agents)
    selection = ClackUI.clack_select("Agent Binding", choices=choices)

    if selection == "__none__":
        return None, False, None
    if selection == "__create__":
        new_agent_id = Prompt.ask("|  New Agent ID", default=default_agent_id)
        model_override = self._pick_agent_model_override()
        return new_agent_id, True, model_override or None
    return selection, False, None

def _build_template_channel_config(self, channel_type: str, token: str) -> dict[str, Any]:
    """Build channel config from one credential token for fleet templates."""
    clean = (token or "").strip()
    if channel_type == "telegram":
        return {"token": clean, "allow_from": []}
    if channel_type == "discord":
        return {"token": clean, "allow_from": []}
    if channel_type == "whatsapp":
        return {"bridge_url": clean or "ws://localhost:3001", "allow_from": []}
    if channel_type == "slack":
        if "|" in clean:
            bot_token, app_token = [part.strip() for part in clean.split("|", 1)]
        else:
            bot_token, app_token = clean, ""
        return {"bot_token": bot_token, "app_token": app_token}
    bridge_defaults = {
        "signal": "ws://localhost:3011",
        "matrix": "ws://localhost:3012",
        "teams": "ws://localhost:3013",
        "google_chat": "ws://localhost:3014",
        "mattermost": "ws://localhost:3015",
        "webex": "ws://localhost:3016",
        "line": "ws://localhost:3017",
    }
    if channel_type in bridge_defaults:
        return {"bridge_url": clean or bridge_defaults[channel_type], "allow_from": []}
    raise ValueError(f"Unsupported channel type for fleet template: {channel_type}")

def _apply_fleet_template(
    self,
    *,
    template_id: str,
    channel_type: str,
    base_id: str,
    bot_tokens: list[str],
) -> int:
    """Apply fleet template by creating bound agents + channel instances."""
    template = FLEET_TEMPLATES.get(template_id)
    if not template:
        raise ValueError(f"Unknown fleet template: {template_id}")
    if not bot_tokens:
        raise ValueError("bot_tokens cannot be empty")

    roles = get_template_roles(template_id)
    if not roles:
        raise ValueError(f"Template '{template_id}' has no role definitions")

    created = 0
    clean_base = (base_id or "fleet").strip().replace(" ", "_") or "fleet"
    max_items = min(len(roles), len(bot_tokens))

    for index in range(max_items):
        role_cfg = roles[index]
        role = str(role_cfg.get("role", f"role_{index + 1}")).strip().replace(" ", "_")
        model = role_cfg.get("default_model")

        agent_id = f"{clean_base}_{role}"
        bound_agent = self._ensure_agent_exists(agent_id, model_override=model)
        config_dict = self._build_template_channel_config(channel_type, bot_tokens[index])

        self._add_channel_instance_record(
            instance_id=agent_id,
            channel_type=channel_type,
            config_dict=config_dict,
            agent_binding=bound_agent,
            auto_create_agent=False,
        )
        created += 1

    return created
