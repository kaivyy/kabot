"""SetupWizard section methods: channels."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Optional

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt

from kabot.cli.fleet_templates import FLEET_TEMPLATES, get_template_roles
from kabot.cli.wizard.channel_menu import build_channel_menu_options
from kabot.cli.wizard.ui import ClackUI
from kabot.config.loader import load_config
from kabot.config.schema import AgentBinding, AgentBindingMatch, AgentConfig, ChannelInstance
from kabot.utils.workspace_templates import ensure_workspace_templates

console = Console()

def _configure_channels(self):
    # Mark section as in progress
    self._save_setup_state("channels", completed=False, in_progress=True)

    configured_channels = []

    while True:
        ClackUI.section_start("Channels")

        c = self.config.channels
        options = build_channel_menu_options(c)
        if not c.instances:
            console.print(
                "|  [dim]Need multi-bot? Choose 'Manage Channel Instances (Add Multiple Bots)'[/dim]"
            )

        choice = ClackUI.clack_select("Select channel to configure", choices=options)

        if choice == "back" or choice is None:
            ClackUI.section_end()
            break

        if choice == "instances":
            self._configure_channel_instances()

        elif choice == "telegram":
            if Confirm.ask("|  Enable Telegram", default=c.telegram.enabled):
                token = self._prompt_secret_value("|  Bot Token", c.telegram.token)
                if token:
                    c.telegram.token = token
                    c.telegram.allow_from = self._prompt_allow_from_list(
                        "Allowed Telegram users (ID/username)",
                        c.telegram.allow_from,
                    )
                    c.telegram.enabled = True
                    self._configure_legacy_channel_ai_binding("telegram")
                    configured_channels.append("telegram")
                    console.print("|  [green]OK Telegram configured[/green]")
            else:
                c.telegram.enabled = False

        elif choice == "whatsapp":
            self._configure_whatsapp()
            if c.whatsapp.enabled:
                self._configure_legacy_channel_ai_binding("whatsapp")
                configured_channels.append("whatsapp")

        elif choice == "discord":
            if Confirm.ask("|  Enable Discord", default=c.discord.enabled):
                token = self._prompt_secret_value("|  Bot Token", c.discord.token)
                if token:
                    c.discord.token = token
                    c.discord.allow_from = self._prompt_allow_from_list(
                        "Allowed Discord users (user ID)",
                        c.discord.allow_from,
                    )
                    c.discord.enabled = True
                    self._configure_legacy_channel_ai_binding("discord")
                    configured_channels.append("discord")

                # Optional advanced fields
                if Confirm.ask("|  Configure Gateway/Intents (Advanced)"):
                    c.discord.gateway_url = Prompt.ask("|  Gateway URL", default=c.discord.gateway_url)
                    intents_str = Prompt.ask(
                        "|  Intents (bitmask or comma separated)",
                        default=self._discord_intents_default_value(c.discord.intents),
                    )
                    if intents_str:
                        parsed_intents = self._parse_discord_intents(intents_str)
                        if parsed_intents is None:
                            console.print("|  [red]Invalid intents format[/red]")
                        else:
                            c.discord.intents = parsed_intents
            else:
                c.discord.enabled = False

        elif choice == "slack":
            if Confirm.ask("|  Enable Slack", default=c.slack.enabled):
                bot_token = self._prompt_secret_value("|  Bot Token (xoxb-...)", c.slack.bot_token)
                app_token = self._prompt_secret_value("|  App Token (xapp-...)", c.slack.app_token)
                if bot_token and app_token:
                    c.slack.bot_token = bot_token
                    c.slack.app_token = app_token
                    if Confirm.ask("|  Configure Slack access policy", default=True):
                        dm_policy = ClackUI.clack_select(
                            "Slack DM policy",
                            choices=[
                                questionary.Choice("Open (any DM user)", value="open"),
                                questionary.Choice("Allowlist only", value="allowlist"),
                            ],
                            default=c.slack.dm.policy,
                        )
                        if dm_policy:
                            c.slack.dm.policy = dm_policy
                        if c.slack.dm.policy == "allowlist":
                            c.slack.dm.allow_from = self._prompt_allow_from_list(
                                "Allowed Slack DM users (user ID)",
                                c.slack.dm.allow_from,
                            )
                        else:
                            c.slack.dm.allow_from = []

                        group_policy = ClackUI.clack_select(
                            "Slack group policy",
                            choices=[
                                questionary.Choice("Mention only (recommended)", value="mention"),
                                questionary.Choice("Open", value="open"),
                                questionary.Choice("Allowlist only", value="allowlist"),
                            ],
                            default=c.slack.group_policy,
                        )
                        if group_policy:
                            c.slack.group_policy = group_policy
                        if c.slack.group_policy == "allowlist":
                            c.slack.group_allow_from = self._prompt_allow_from_list(
                                "Allowed Slack channel IDs",
                                c.slack.group_allow_from,
                            )
                        else:
                            c.slack.group_allow_from = []
                    self._configure_legacy_channel_ai_binding("slack")
                    c.slack.enabled = True
                    configured_channels.append("slack")
            else:
                c.slack.enabled = False

        elif choice == "feishu":
            if Confirm.ask("|  Enable Feishu", default=c.feishu.enabled):
                app_id = self._prompt_secret_value("|  App ID", c.feishu.app_id)
                app_secret = self._prompt_secret_value("|  App Secret", c.feishu.app_secret)
                if app_id and app_secret:
                    c.feishu.app_id = app_id
                    c.feishu.app_secret = app_secret
                    c.feishu.allow_from = self._prompt_allow_from_list(
                        "Allowed Feishu users (open_id)",
                        c.feishu.allow_from,
                    )
                    c.feishu.enabled = True
                    self._configure_legacy_channel_ai_binding("feishu")
                    configured_channels.append("feishu")
            else:
                c.feishu.enabled = False

        elif choice == "dingtalk":
            if Confirm.ask("|  Enable DingTalk", default=c.dingtalk.enabled):
                c.dingtalk.client_id = self._prompt_secret_value(
                    "|  Client ID (AppKey)",
                    c.dingtalk.client_id,
                )
                c.dingtalk.client_secret = self._prompt_secret_value(
                    "|  Client Secret (AppSecret)",
                    c.dingtalk.client_secret,
                )
                c.dingtalk.allow_from = self._prompt_allow_from_list(
                    "Allowed DingTalk users (staff_id)",
                    c.dingtalk.allow_from,
                )
                c.dingtalk.enabled = True
                self._configure_legacy_channel_ai_binding("dingtalk")
                configured_channels.append("dingtalk")
            else:
                c.dingtalk.enabled = False

        elif choice == "qq":
            if Confirm.ask("|  Enable QQ", default=c.qq.enabled):
                c.qq.app_id = self._prompt_secret_value("|  App ID", c.qq.app_id)
                c.qq.secret = self._prompt_secret_value("|  App Secret", c.qq.secret)
                c.qq.allow_from = self._prompt_allow_from_list(
                    "Allowed QQ users (openid)",
                    c.qq.allow_from,
                )
                c.qq.enabled = True
                self._configure_legacy_channel_ai_binding("qq")
                configured_channels.append("qq")
            else:
                c.qq.enabled = False

        elif choice == "email":
            if Confirm.ask("|  Enable Email Channel", default=c.email.enabled):
                console.print("|  [bold]IMAP (Incoming)[/bold]")
                c.email.imap_host = self._prompt_secret_value("|  IMAP Host", c.email.imap_host)
                c.email.imap_username = self._prompt_secret_value("|  IMAP User", c.email.imap_username)
                if Confirm.ask("|  Update IMAP Password"):
                    c.email.imap_password = Prompt.ask("|  IMAP Password", password=True)

                console.print("|  [bold]SMTP (Outgoing)[/bold]")
                c.email.smtp_host = self._prompt_secret_value("|  SMTP Host", c.email.smtp_host)
                c.email.smtp_username = self._prompt_secret_value("|  SMTP User", c.email.smtp_username)
                if Confirm.ask("|  Update SMTP Password"):
                    c.email.smtp_password = Prompt.ask("|  SMTP Password", password=True)

                c.email.from_address = self._prompt_secret_value(
                    "|  Sender Address (From)",
                    c.email.from_address,
                )
                c.email.allow_from = self._prompt_allow_from_list(
                    "Allowed email senders (email address)",
                    c.email.allow_from,
                )
                c.email.enabled = True
                self._configure_legacy_channel_ai_binding("email")
                configured_channels.append("email")
            else:
                c.email.enabled = False

        ClackUI.section_end()

    # Mark as completed and save configuration
    self._save_setup_state(
        "channels",
        completed=True,
        configured_channels=configured_channels,
        instance_count=len(c.instances) if c.instances else 0,
    )

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

def _configure_channel_instances(self):
    """Configure multiple channel instances (e.g., 4 Telegram bots, 4 Discord bots)."""
    while True:
        ClackUI.section_start("Channel Instances")

        if not self.config.channels.instances:
            console.print("|  [dim]No channel instances yet.[/dim]")
            console.print("|  [dim]Use 'Add Instance' for one bot, or 'Quick Add Multiple' for multi-bot setup.[/dim]")
            console.print("|")

        if self.config.channels.instances:
            console.print("|  [bold]Current Instances:[/bold]")
            for idx, inst in enumerate(self.config.channels.instances, 1):
                status = "[green]ON[/green]" if inst.enabled else "[dim]OFF[/dim]"
                binding = f" -> {inst.agent_binding}" if inst.agent_binding else ""
                console.print(f"|    {idx}. [{inst.type}] {inst.id} {status}{binding}")
            console.print("|")

        options = [
            questionary.Choice("Add Instance", value="add"),
            questionary.Choice("Quick Add Multiple", value="bulk"),
            questionary.Choice("Apply Fleet Template", value="template"),
            questionary.Choice("Edit Instance", value="edit"),
            questionary.Choice("Delete Instance", value="delete"),
            questionary.Choice("Back", value="back"),
        ]
        choice = ClackUI.clack_select("Manage Instances", choices=options)

        if choice == "back" or choice is None:
            ClackUI.section_end()
            break
        if choice == "add":
            self._add_channel_instance()
        elif choice == "bulk":
            self._bulk_add_channel_instances()
        elif choice == "template":
            self._apply_fleet_template_interactive()
        elif choice == "edit":
            self._edit_channel_instance()
        elif choice == "delete":
            self._delete_channel_instance()

def _add_channel_instance(self):
    """Add a single channel instance with optional dedicated agent creation."""
    instance_id = Prompt.ask("|  Instance ID (e.g., work_bot, personal_bot)").strip()
    if not instance_id:
        console.print("|  [yellow]Cancelled[/yellow]")
        return

    channel_type = ClackUI.clack_select(
        "Channel Type",
        choices=[
            questionary.Choice("Telegram", value="telegram"),
            questionary.Choice("Discord", value="discord"),
            questionary.Choice("WhatsApp", value="whatsapp"),
            questionary.Choice("Slack", value="slack"),
            questionary.Choice("Signal", value="signal"),
            questionary.Choice("Matrix", value="matrix"),
            questionary.Choice("Teams", value="teams"),
            questionary.Choice("Google Chat", value="google_chat"),
            questionary.Choice("Mattermost", value="mattermost"),
            questionary.Choice("Webex", value="webex"),
            questionary.Choice("LINE", value="line"),
        ],
    )
    if not channel_type:
        return

    config_dict = self._prompt_instance_config(channel_type)
    if not config_dict:
        console.print("|  [yellow]Cancelled[/yellow]")
        return

    agent_binding, auto_create_agent, model_override = self._prompt_agent_binding(instance_id)
    instance = self._add_channel_instance_record(
        instance_id=instance_id,
        channel_type=channel_type,
        config_dict=config_dict,
        agent_binding=agent_binding,
        auto_create_agent=auto_create_agent,
        model_override=model_override,
    )
    console.print(f"|  [green]OK[/green] Added {channel_type} instance '{instance.id}'")

def _bulk_add_channel_instances(self):
    """Quick flow for adding many instances at once."""
    channel_type = ClackUI.clack_select(
        "Bulk Channel Type",
        choices=[
            questionary.Choice("Telegram", value="telegram"),
            questionary.Choice("Discord", value="discord"),
            questionary.Choice("WhatsApp", value="whatsapp"),
            questionary.Choice("Slack", value="slack"),
            questionary.Choice("Signal", value="signal"),
            questionary.Choice("Matrix", value="matrix"),
            questionary.Choice("Teams", value="teams"),
            questionary.Choice("Google Chat", value="google_chat"),
            questionary.Choice("Mattermost", value="mattermost"),
            questionary.Choice("Webex", value="webex"),
            questionary.Choice("LINE", value="line"),
        ],
    )
    if not channel_type:
        return

    count_raw = Prompt.ask("|  Number of bots to add", default="2").strip()
    try:
        count = int(count_raw)
    except ValueError:
        console.print("|  [red]Invalid count[/red]")
        return
    if count < 1 or count > 20:
        console.print("|  [red]Count must be 1-20[/red]")
        return

    prefix = Prompt.ask("|  Instance ID prefix", default=f"{channel_type}_bot").strip() or f"{channel_type}_bot"
    auto_bind = Confirm.ask("|  Auto-create dedicated agent for each bot", default=True)
    shared_model_override = None
    if auto_bind and Confirm.ask("|  Set one model for all new agents", default=False):
        shared_model_override = self._pick_agent_model_override()

    for index in range(1, count + 1):
        console.print(f"|  [bold]Bot #{index}[/bold]")
        default_instance_id = f"{prefix}_{index}"
        instance_id = Prompt.ask(f"|  Instance ID #{index}", default=default_instance_id).strip() or default_instance_id

        config_dict = self._prompt_instance_config(channel_type)
        if not config_dict:
            console.print("|  [yellow]Skipped (missing config)[/yellow]")
            continue

        agent_binding = None
        auto_create_agent = False
        model_override = shared_model_override
        if auto_bind:
            agent_binding = instance_id
            auto_create_agent = True
        else:
            agent_binding, auto_create_agent, model_override = self._prompt_agent_binding(instance_id)

        instance = self._add_channel_instance_record(
            instance_id=instance_id,
            channel_type=channel_type,
            config_dict=config_dict,
            agent_binding=agent_binding,
            auto_create_agent=auto_create_agent,
            model_override=model_override,
        )
        console.print(f"|  [green]OK[/green] Added {channel_type} instance '{instance.id}'")

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

def _apply_fleet_template_interactive(self) -> None:
    """Interactive flow to apply predefined fleet templates."""
    template_choices = [
        questionary.Choice(f"{meta.get('label', key)}", value=key)
        for key, meta in FLEET_TEMPLATES.items()
    ]
    template_id = ClackUI.clack_select("Fleet Template", choices=template_choices)
    if not template_id:
        return

    channel_type = ClackUI.clack_select(
        "Channel Type",
        choices=[
            questionary.Choice("Telegram", value="telegram"),
            questionary.Choice("Discord", value="discord"),
            questionary.Choice("WhatsApp", value="whatsapp"),
            questionary.Choice("Slack", value="slack"),
            questionary.Choice("Signal", value="signal"),
            questionary.Choice("Matrix", value="matrix"),
            questionary.Choice("Teams", value="teams"),
            questionary.Choice("Google Chat", value="google_chat"),
            questionary.Choice("Mattermost", value="mattermost"),
            questionary.Choice("Webex", value="webex"),
            questionary.Choice("LINE", value="line"),
        ],
    )
    if not channel_type:
        return

    roles = get_template_roles(template_id)
    base_id = Prompt.ask("|  Fleet base id", default="team").strip() or "team"

    token_hint = "Bot Token"
    if channel_type == "slack":
        token_hint = "Bot token|App token"
    elif channel_type in {
        "whatsapp",
        "signal",
        "matrix",
        "teams",
        "google_chat",
        "mattermost",
        "webex",
        "line",
    }:
        token_hint = "Bridge URL"

    bot_tokens: list[str] = []
    for idx, role_cfg in enumerate(roles, 1):
        role = role_cfg.get("role", f"role_{idx}")
        value = Prompt.ask(f"|  {token_hint} for {role}").strip()
        if not value:
            console.print("|  [yellow]Skipped empty credential[/yellow]")
            continue
        bot_tokens.append(value)

    if not bot_tokens:
        console.print("|  [yellow]Cancelled (no credentials provided)[/yellow]")
        return

    created = self._apply_fleet_template(
        template_id=template_id,
        channel_type=channel_type,
        base_id=base_id,
        bot_tokens=bot_tokens,
    )
    console.print(f"|  [green]OK[/green] Applied template '{template_id}' with {created} bot(s)")

def _edit_channel_instance(self):
    """Edit an existing channel instance."""
    if not self.config.channels.instances:
        console.print("|  [yellow]No instances configured[/yellow]")
        return

    choices = []
    for idx, inst in enumerate(self.config.channels.instances, 1):
        label = f"{idx}. [{inst.type}] {inst.id}"
        choices.append(questionary.Choice(label, value=idx - 1))

    idx = ClackUI.clack_select("Select instance to edit", choices=choices)
    if idx is None:
        return

    instance = self.config.channels.instances[idx]
    instance.enabled = Confirm.ask(f"|  Enable {instance.id}", default=instance.enabled)

    if Confirm.ask("|  Change agent binding", default=False):
        binding, auto_create, model_override = self._prompt_agent_binding(instance.id)
        if auto_create and binding:
            instance.agent_binding = self._ensure_agent_exists(binding, model_override=model_override)
        else:
            instance.agent_binding = binding

    self._edit_instance_channel_config(instance)

    if instance.type in {
        "telegram",
        "discord",
        "whatsapp",
        "signal",
        "matrix",
        "teams",
        "google_chat",
        "mattermost",
        "webex",
        "line",
    }:
        if Confirm.ask("|  Edit allowFrom list", default=False):
            current_allow = instance.config.get("allow_from", [])
            label = {
                "telegram": "Allowed users for this Telegram bot",
                "discord": "Allowed users for this Discord bot",
                "whatsapp": "Allowed WhatsApp numbers for this bot",
                "signal": "Allowed users for this Signal bot",
                "matrix": "Allowed users for this Matrix bot",
                "teams": "Allowed users for this Teams bot",
                "google_chat": "Allowed users for this Google Chat bot",
                "mattermost": "Allowed users for this Mattermost bot",
                "webex": "Allowed users for this Webex bot",
                "line": "Allowed users for this LINE bot",
            }.get(instance.type, "Allowed users")
            instance.config["allow_from"] = self._prompt_allow_from_list(label, current_allow)

    console.print(f"|  [green]OK[/green] Updated {instance.id}")


def _edit_instance_channel_config(self, instance: ChannelInstance) -> None:
    """Edit per-channel instance credentials while preserving secrets by default."""
    if instance.type == "telegram":
        if Confirm.ask("|  Edit bot token", default=False):
            current_token = str(instance.config.get("token") or "")
            instance.config["token"] = self._prompt_secret_value("|  Bot Token", current_token)
        return

    if instance.type == "discord":
        if Confirm.ask("|  Edit bot token", default=False):
            current_token = str(instance.config.get("token") or "")
            instance.config["token"] = self._prompt_secret_value("|  Bot Token", current_token)
        return

    if instance.type in {
        "whatsapp",
        "signal",
        "matrix",
        "teams",
        "google_chat",
        "mattermost",
        "webex",
        "line",
    }:
        if Confirm.ask("|  Edit bridge URL", default=False):
            current_url = str(instance.config.get("bridge_url") or "ws://localhost:3001")
            next_url = Prompt.ask("|  Bridge URL", default=current_url).strip()
            if next_url:
                instance.config["bridge_url"] = next_url
        return

    if instance.type == "slack":
        if Confirm.ask("|  Edit bot token", default=False):
            current_bot = str(instance.config.get("bot_token") or "")
            instance.config["bot_token"] = self._prompt_secret_value(
                "|  Bot Token (xoxb-...)",
                current_bot,
            )
        if Confirm.ask("|  Edit app token", default=False):
            current_app = str(instance.config.get("app_token") or "")
            instance.config["app_token"] = self._prompt_secret_value(
                "|  App Token (xapp-...)",
                current_app,
            )
        return

def _delete_channel_instance(self):
    """Delete a channel instance."""
    if not self.config.channels.instances:
        console.print("|  [yellow]No instances configured[/yellow]")
        return

    choices = []
    for idx, inst in enumerate(self.config.channels.instances, 1):
        label = f"{idx}. [{inst.type}] {inst.id}"
        choices.append(questionary.Choice(label, value=idx - 1))

    idx = ClackUI.clack_select("Select instance to delete", choices=choices)
    if idx is None:
        return

    instance = self.config.channels.instances[idx]
    if Confirm.ask(f"|  Delete {instance.id}", default=False):
        self.config.channels.instances.pop(idx)
        console.print(f"|  [green]OK[/green] Deleted {instance.id}")

def _configure_whatsapp(self):
    """Special flow for WhatsApp Bridge."""
    # Check if we should enable/disable first
    if not Confirm.ask("|  Enable WhatsApp", default=self.config.channels.whatsapp.enabled):
        self.config.channels.whatsapp.enabled = False
        return

    self.config.channels.whatsapp.enabled = True
    self.config.channels.whatsapp.allow_from = self._prompt_allow_from_list(
        "Allowed WhatsApp numbers",
        self.config.channels.whatsapp.allow_from,
    )

    # Bridge setup logic
    try:
        from kabot.cli.bridge_utils import (
            get_bridge_dir,
            is_bridge_reachable,
            run_bridge_login,
            stop_bridge_processes,
            start_bridge_background,
        )

        # Check/Install Bridge
        with console.status("|  Checking WhatsApp Bridge..."):
            get_bridge_dir()

        console.print("|  [green]OK Bridge installed[/green]")

        if Confirm.ask("|  Connect now (Show QR Code)"):
            console.print("|")
            console.print("|  [yellow]Starting bridge for QR login (auto-return after connected).[/yellow]")
            console.print("|")
            try:
                bridge_url = self.config.channels.whatsapp.bridge_url
                restart_if_running = False
                if is_bridge_reachable(bridge_url):
                    console.print(f"|  [yellow]Bridge already running at {bridge_url}.[/yellow]")
                    restart_if_running = Confirm.ask(
                        "|  Restart running bridge to show QR in this terminal",
                        default=True,
                    )
                    if restart_if_running:
                        stopped = stop_bridge_processes(bridge_url=bridge_url)
                        if stopped:
                            console.print(
                                f"|  [dim]Stopped existing bridge process(es): "
                                f"{', '.join(str(pid) for pid in stopped)}[/dim]"
                            )
                        else:
                            console.print(
                                "|  [yellow]Could not identify a safe bridge process to stop. "
                                "Will reuse existing process if still active.[/yellow]"
                            )

                connected = run_bridge_login(
                    stop_when_connected=True,
                    timeout_seconds=180,
                    bridge_url=bridge_url,
                    restart_if_running=restart_if_running,
                )
                if connected:
                    console.print("|  [green]OK[/green] WhatsApp connected.")
                else:
                    console.print("|  [yellow]Connection not confirmed yet. You can retry later.[/yellow]")
            except KeyboardInterrupt:
                console.print("\n|  [yellow]Returned to wizard.[/yellow]")
            except Exception as e:
                console.print(f"|  [red]Error running bridge: {e}[/red]")

        if Confirm.ask("|  Keep WhatsApp bridge running in background now", default=True):
            bridge_url = self.config.channels.whatsapp.bridge_url
            if is_bridge_reachable(bridge_url):
                console.print("|  [green]OK[/green] Bridge already running.")
            else:
                started = start_bridge_background(bridge_url=bridge_url, wait_seconds=20.0)
                if started:
                    console.print("|  [green]OK[/green] Bridge running in background.")
                else:
                    console.print(
                        "|  [yellow]Could not confirm background bridge startup. "
                        "You can run 'kabot channels login' manually.[/yellow]"
                    )
    except ImportError:
        console.print("|  [red]Could not load CLI commands. Please install dependencies.[/red]")
    except Exception as e:
        console.print(f"|  [red]Bridge setup failed: {e}[/red]")

def bind_channels_sections(cls):
    cls._configure_channels = _configure_channels
    cls._discord_intents_default_value = _discord_intents_default_value
    cls._parse_discord_intents = _parse_discord_intents
    cls._parse_allow_from_values = staticmethod(_parse_allow_from_values)
    cls._prompt_secret_value = _prompt_secret_value
    cls._prompt_allow_from_list = _prompt_allow_from_list
    cls._pick_agent_model_override = _pick_agent_model_override
    cls._find_channel_default_binding = _find_channel_default_binding
    cls._upsert_channel_default_binding = _upsert_channel_default_binding
    cls._remove_channel_default_binding = _remove_channel_default_binding
    cls._configure_legacy_channel_ai_binding = _configure_legacy_channel_ai_binding
    cls._instance_id_exists = _instance_id_exists
    cls._next_available_instance_id = _next_available_instance_id
    cls._ensure_agent_exists = _ensure_agent_exists
    cls._add_channel_instance_record = _add_channel_instance_record
    cls._prompt_instance_config = _prompt_instance_config
    cls._prompt_agent_binding = _prompt_agent_binding
    cls._configure_channel_instances = _configure_channel_instances
    cls._add_channel_instance = _add_channel_instance
    cls._bulk_add_channel_instances = _bulk_add_channel_instances
    cls._build_template_channel_config = _build_template_channel_config
    cls._apply_fleet_template = _apply_fleet_template
    cls._apply_fleet_template_interactive = _apply_fleet_template_interactive
    cls._edit_channel_instance = _edit_channel_instance
    cls._edit_instance_channel_config = _edit_instance_channel_config
    cls._delete_channel_instance = _delete_channel_instance
    cls._configure_whatsapp = _configure_whatsapp
    return cls
