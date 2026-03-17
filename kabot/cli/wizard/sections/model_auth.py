"""SetupWizard section methods: model_auth."""

from __future__ import annotations

from typing import Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import questionary
from rich.console import Console
from rich.prompt import Confirm, Prompt

from kabot.cli.wizard.ui import ClackUI
from kabot.config.loader import load_config

console = Console()

from kabot.cli.wizard.sections.model_auth_helpers import (  # noqa: E402,I001
    _sync_provider_credentials_from_disk,
    _provider_has_credentials,
    _provider_config_key_for_auth,
    _provider_has_saved_credentials,
    _providers_with_saved_credentials,
    _model_allowed_by_provider_credentials,
    _current_model_display,
    _current_model_chain,
    _set_model_chain,
    _provider_model_prefixes,
    _model_matches_provider,
    _normalize_scoped_manual_model_input,
    _build_model_chain_from_provider_selections,
    _apply_model_chain_from_provider_selections,
    _apply_post_login_defaults,
    _recommended_auto_model_chain,
    _apply_auto_default_model_chain,
    _show_auto_model_chain_summary,
)

def _configure_model(self):
    ClackUI.section_start("Model & Auth")

    # Mark section as in progress
    self._save_setup_state("auth", completed=False, in_progress=True)

    from kabot.auth.manager import AuthManager
    from kabot.auth.menu import get_auth_choices

    manager = AuthManager()
    auth_choices = get_auth_choices()
    state = self._load_setup_state()
    user_selections = state.get("user_selections", {})
    configured_providers = [
        str(p).strip()
        for p in (user_selections.get("selected_providers", []) or [])
        if str(p).strip()
    ]
    provider_models = {
        str(k).strip(): str(v).strip()
        for k, v in (user_selections.get("provider_models", {}) or {}).items()
        if str(k).strip() and str(v).strip()
    }
    provider_order = [
        str(p).strip()
        for p in (user_selections.get("provider_model_order", []) or [])
        if str(p).strip()
    ]
    for provider_id in provider_models:
        if provider_id not in provider_order:
            provider_order.append(provider_id)

    while True:
        login_label = "Provider Login (Setup API Keys/OAuth + Pick Model)"
        picker_label = "Select Model (Primary/Fallback)"
        fallback_label = "Manage Fallbacks (Select with Space)"
        reorder_label = "Edit Fallback Order (Up/Down)"
        choice = ClackUI.clack_select(
            "Select an option:",
            choices=[
                questionary.Choice(login_label, value="login"),
                questionary.Choice(picker_label, value="picker"),
                questionary.Choice(fallback_label, value="fallbacks"),
                questionary.Choice(reorder_label, value="reorder"),
                questionary.Choice("Back", value="back"),
            ]
        )

        if choice == "back" or choice is None:
            break

        if choice == "login":
            p_options = [questionary.Choice(c['name'], value=c['value']) for c in auth_choices]
            provider_val = ClackUI.clack_select("Select provider to login", choices=p_options)

            if not provider_val:
                continue

            already_configured = self._provider_has_saved_credentials(provider_val)
            auth_ok = False
            did_fresh_login = False
            if already_configured:
                action = ClackUI.clack_select(
                    f"Credentials already exist for '{provider_val}'. Choose action",
                    choices=[
                        questionary.Choice("Use saved credentials (skip login)", value="use_saved"),
                        questionary.Choice("Re-enter API key / OAuth", value="relogin"),
                        questionary.Choice("Back", value="back"),
                    ],
                )
                if action in {None, "back"}:
                    continue
                if action == "use_saved":
                    console.print("|  [green]Using saved credentials.[/green]")
                    auth_ok = True
                elif action == "relogin":
                    auth_ok = manager.login(provider_val)
                    did_fresh_login = auth_ok
            else:
                auth_ok = manager.login(provider_val)
                did_fresh_login = auth_ok

            if auth_ok:
                self._sync_provider_credentials_from_disk()
                if provider_val not in configured_providers:
                    configured_providers.append(provider_val)
                # Validate only on fresh login, not when reusing existing credentials.
                if did_fresh_login:
                    self._validate_provider_credentials(provider_val)
                selected_model = self._model_browser(
                    provider_val,
                    apply_selection=False,
                    preferred_model=provider_models.get(provider_val),
                    prefer_first_provider_model=True,
                )
                if selected_model:
                    provider_models[provider_val] = selected_model
                    if provider_val not in provider_order:
                        provider_order.append(provider_val)
                    updated = self._apply_model_chain_from_provider_selections(
                        provider_models=provider_models,
                        provider_order=provider_order,
                    )
                    self._show_auto_model_chain_summary(updated)
                else:
                    console.print("|  [dim]Model selection skipped (Back/Keep current). Chain unchanged.[/dim]")

        elif choice == "picker":
            self._model_picker(allowed_provider_ids=self._providers_with_saved_credentials())
        elif choice == "fallbacks":
            self._manage_fallbacks(allowed_provider_ids=self._providers_with_saved_credentials())
        elif choice == "reorder":
            self._reorder_fallbacks()

    # Save configured providers and mark as completed
    self._save_setup_state("auth", completed=True,
                         configured_providers=configured_providers,
                         provider_models=provider_models,
                         provider_model_order=provider_order,
                         default_model=self.config.agents.defaults.model)

    # Update user selections
    state = self._load_setup_state()
    selections = state.setdefault("user_selections", {})
    selections["selected_providers"] = configured_providers
    selections["provider_models"] = provider_models
    selections["provider_model_order"] = provider_order
    selections["default_model"] = self.config.agents.defaults.model
    self._write_setup_state(state)
    ClackUI.section_end()

def _configure_memory(self) -> None:
    """Configure memory backend settings."""
    from kabot.config.loader import save_config
    from kabot.memory.memory_factory import SUPPORTED_BACKENDS

    ClackUI.section_start("Memory Configuration")

    current = self.config.memory.backend
    console.print(f"|  [dim]Current backend: {current}[/dim]")

    backend = ClackUI.clack_select(
        "Memory backend",
        choices=[
            questionary.Choice("Hybrid (ChromaDB + SQLite + BM25) - Full power", value="hybrid"),
            questionary.Choice("SQLite Only - Lightweight, no embeddings", value="sqlite_only"),
            questionary.Choice("Disabled - No memory at all", value="disabled"),
        ],
        default=current,
    )
    if backend is None:
        ClackUI.section_end()
        return

    if backend not in SUPPORTED_BACKENDS:
        console.print(
            f"|  [red]Invalid backend '{backend}'. Supported: {', '.join(sorted(SUPPORTED_BACKENDS))}[/red]"
        )
        ClackUI.section_end()
        return

    self.config.memory.backend = backend

    if backend == "hybrid":
        current_emb = self.config.memory.embedding_provider
        emb_provider = ClackUI.clack_select(
            "Embedding provider",
            choices=[
                questionary.Choice("Sentence-Transformers (Local, recommended)", value="sentence"),
                questionary.Choice("Ollama (Requires running Ollama server)", value="ollama"),
            ],
            default=current_emb,
        )
        if emb_provider:
            self.config.memory.embedding_provider = emb_provider

    save_config(self.config)
    self._save_setup_state("memory", completed=True, backend=backend)
    console.print(f"|  [green]OK Memory backend set to: {backend}[/green]")
    ClackUI.section_end()

def _model_picker(
    self,
    provider_id: Optional[str] = None,
    allowed_provider_ids: Optional[list[str] | set[str]] = None,
):
    from kabot.cli.model_validator import resolve_alias
    from kabot.providers.model_status import get_model_status, get_status_indicator

    normalized_allowed_provider_ids = [
        str(pid).strip()
        for pid in (allowed_provider_ids or [])
        if str(pid).strip()
    ]
    if provider_id is None and not normalized_allowed_provider_ids:
        normalized_allowed_provider_ids = self._providers_with_saved_credentials()

    if provider_id is None and not normalized_allowed_provider_ids:
        console.print("|  [yellow]No providers with saved credentials found.[/yellow]")
        console.print("|  [dim]Login provider first via Provider Login (API key/OAuth).[/dim]")
        return None

    if provider_id and normalized_allowed_provider_ids and provider_id not in normalized_allowed_provider_ids:
        console.print(
            f"|  [red]Provider '{provider_id}' has no saved credentials. Configure API key/OAuth first.[/red]"
        )
        return None

    # Popular aliases section
    popular_aliases = [
        ("codex", "OpenAI GPT-5.1 Codex (Advanced Coding)"),
        ("sonnet", "Claude 3.5 Sonnet (Latest, 200K context)"),
        ("gemini", "Google Gemini 1.5 Pro (2M context)"),
        ("gpt4o", "OpenAI GPT-4o (Multi-modal)"),
    ]

    current_display = self._current_model_display()
    m_choices = [
        questionary.Choice(f"Keep current ({current_display})", value="keep"),
    ]

    # Add popular aliases
    for alias, description in popular_aliases:
        model_id = resolve_alias(alias)
        if model_id:
            if not self._model_allowed_by_provider_credentials(model_id, normalized_allowed_provider_ids):
                continue
            status = get_model_status(model_id)
            indicator = get_status_indicator(status)
            m_choices.append(
                questionary.Choice(f"{alias:10} - {description} {indicator}", value=f"alias:{alias}")
            )

    # Add browse and manual options
    m_choices.extend([
        questionary.Choice("Browse All Models (by provider)", value="browse"),
        questionary.Choice("Enter Model ID or Alias Manually", value="manual"),
    ])

    selected = ClackUI.clack_select("Select default model (or use alias)", choices=m_choices)

    if selected == "keep" or selected is None:
        return None
    elif selected == "browse":
        return self._model_browser(
            provider_id,
            allowed_provider_ids=normalized_allowed_provider_ids or None,
        )
    elif selected == "manual":
        return self._manual_model_entry(
            provider_id=provider_id,
            allowed_provider_ids=normalized_allowed_provider_ids or None,
        )
    elif selected.startswith("alias:"):
        alias = selected.split(":")[1]
        model_id = resolve_alias(alias)
        if model_id:
            if not self._model_allowed_by_provider_credentials(model_id, normalized_allowed_provider_ids):
                console.print(
                    "|  [red]Provider for this model has no saved credentials. Login first in Provider Login.[/red]"
                )
                return None
            if self._confirm_and_set_model(model_id):
                return model_id
    return None

def _model_browser(
    self,
    provider_id: Optional[str] = None,
    apply_selection: bool = True,
    preferred_model: Optional[str] = None,
    prefer_first_provider_model: bool = False,
    allowed_provider_ids: Optional[list[str] | set[str]] = None,
):
    """Browse models by provider with status indicators."""
    from kabot.providers.model_status import get_model_status, get_status_indicator

    normalized_allowed_provider_ids = [
        str(pid).strip()
        for pid in (allowed_provider_ids or [])
        if str(pid).strip()
    ]

    all_models = self.registry.list_models()
    if normalized_allowed_provider_ids:
        all_models = [
            m
            for m in all_models
            if self._model_allowed_by_provider_credentials(m.id, normalized_allowed_provider_ids)
        ]

    if provider_id and normalized_allowed_provider_ids and provider_id not in normalized_allowed_provider_ids:
        console.print(
            f"|  [red]Provider '{provider_id}' has no saved credentials. Configure API key/OAuth first.[/red]"
        )
        return None

    if provider_id is None:
        provider_counts: dict[str, int] = {}
        for m in all_models:
            provider_counts[m.provider] = provider_counts.get(m.provider, 0) + 1

        p_choices = [questionary.Choice(f"All providers ({len(all_models)} models)", value="all")]
        for p_name, count in sorted(provider_counts.items()):
            p_choices.append(questionary.Choice(f"{p_name} ({count} models)", value=p_name))

        p_val = ClackUI.clack_select("Filter models by provider", choices=p_choices)
        if p_val == "all":
            provider_id = None
        else:
            provider_id = p_val

    if provider_id:
        models = [
            m for m in all_models
            if m.provider in self._provider_model_prefixes(provider_id)
            or self._model_matches_provider(m.id, provider_id)
        ]
    else:
        models = all_models
    models.sort(key=lambda x: (not x.is_premium, x.id))

    if provider_id and not models:
        console.print(f"|  [yellow]No catalog models found for provider '{provider_id}'.[/yellow]")
        console.print("|  [dim]You can enter a model ID manually.[/dim]")

    current_display = self._current_model_display()
    keep_label = f"Keep current ({current_display})"
    if provider_id is not None and apply_selection is False:
        keep_label = "Keep existing provider model (no change)"

    m_choices = [
        questionary.Choice(keep_label, value="keep"),
        questionary.Choice("Enter model ID or Alias Manually", value="manual"),
    ]
    status_by_id: dict[str, str] = {}
    verified_models = []
    catalog_models = []
    other_models = []
    for m in models:
        status = get_model_status(m.id)
        status_by_id[m.id] = status
        if status == "working":
            verified_models.append(m)
        elif status == "catalog":
            catalog_models.append(m)
        else:
            other_models.append(m)

    grouped_models = [
        ("Verified Models", verified_models),
        ("Catalog Models", catalog_models),
        ("Other Models", other_models),
    ]
    ordered_models = []
    for title, group in grouped_models:
        if not group:
            continue
        m_choices.append(questionary.Separator(title))
        for m in group:
            status = status_by_id[m.id]
            indicator = get_status_indicator(status)
            label = f"{indicator} {m.id} ({m.name})"
            if m.is_premium:
                label += " *"
            m_choices.append(questionary.Choice(label, value=m.id))
            ordered_models.append(m)

    select_label = "Select default model" if provider_id is None else f"Select model for provider '{provider_id}'"
    default_value = None
    if provider_id is not None and prefer_first_provider_model:
        model_ids = [m.id for m in ordered_models]
        preferred = (preferred_model or "").strip()
        if preferred and preferred in model_ids:
            default_value = preferred
        elif model_ids:
            default_value = model_ids[0]
        else:
            default_value = "manual"
    selected_model = ClackUI.clack_select(select_label, choices=m_choices, default=default_value)

    if selected_model == "keep" or selected_model is None:
        return None
    elif selected_model == "manual":
        return self._manual_model_entry(
            provider_id=provider_id,
            apply_selection=apply_selection,
            allowed_provider_ids=normalized_allowed_provider_ids or None,
        )
    else:
        if self._confirm_and_set_model(selected_model, apply_selection=apply_selection):
            return selected_model
    return None

def _manual_model_entry(
    self,
    provider_id: Optional[str] = None,
    apply_selection: bool = True,
    allowed_provider_ids: Optional[list[str] | set[str]] = None,
):
    """Manual model entry with format hints and validation."""
    from kabot.cli.model_validator import resolve_alias, suggest_alternatives, validate_format

    normalized_allowed_provider_ids = [
        str(pid).strip()
        for pid in (allowed_provider_ids or [])
        if str(pid).strip()
    ]

    console.print("|")
    console.print("|  [bold]Enter Model ID or Alias[/bold]")
    console.print("|")
    console.print("|  Format: [cyan]provider/model-name[/cyan]  OR  [cyan]alias[/cyan]")
    console.print("|  Examples:")
    console.print("|    - openai/gpt-4o")
    console.print("|    - anthropic/claude-3-5-sonnet-20241022")
    console.print("|    - openrouter/qwen/qwen-2.5-vl-72b-instruct:free")
    console.print("|    - codex (alias for openai/gpt-5.1-codex)")
    console.print("|")
    console.print("|  Available aliases: codex, sonnet, gemini, gemini31, gpt4o, o1, kimi, venice, hf-r1, openrouter")
    console.print("|  Type 'help' to see all aliases")
    console.print("|")

    while True:
        user_input = Prompt.ask("|  Your input").strip()

        if user_input.lower() == "back":
            console.print("|  [yellow]Back[/yellow]")
            return None

        if user_input == "help":
            self._show_alias_help()
            continue

        if not user_input:
            console.print("|  [yellow]Cancelled[/yellow]")
            return

        # Try alias resolution first
        model_id = resolve_alias(user_input)
        if model_id:
            if provider_id and not self._model_matches_provider(model_id, provider_id):
                console.print(
                    f"|  [red]X Model '{model_id}' is outside provider scope '{provider_id}'.[/red]"
                )
                continue
            if not self._model_allowed_by_provider_credentials(model_id, normalized_allowed_provider_ids):
                console.print(
                    "|  [red]X Provider for this model has no saved credentials. Login first in Provider Login.[/red]"
                )
                continue
            console.print(f"|  [green]OK Resolved alias '{user_input}' to: {model_id}[/green]")
            if self._confirm_and_set_model(model_id, apply_selection=apply_selection):
                return model_id
            continue

        normalized_input = self._normalize_scoped_manual_model_input(user_input, provider_id)

        # Validate format
        if not validate_format(normalized_input):
            console.print(f"|  [red]X Invalid format: \"{user_input}\"[/red]")
            console.print("|  [dim]Expected: provider/model-name (supports nested ids, e.g. openrouter/vendor/model)[/dim]")
            console.print("|")

            suggestions = suggest_alternatives(user_input)
            if suggestions:
                console.print("|  [yellow]Did you mean one of these[/yellow]")
                for suggestion in suggestions:
                    console.print(f"|    - {suggestion}")
                console.print("|")
            continue

        if provider_id and not self._model_matches_provider(normalized_input, provider_id):
            console.print(
                f"|  [red]X Model '{normalized_input}' is outside provider scope '{provider_id}'.[/red]"
            )
            continue
        if not self._model_allowed_by_provider_credentials(normalized_input, normalized_allowed_provider_ids):
            console.print(
                "|  [red]X Provider for this model has no saved credentials. Login first in Provider Login.[/red]"
            )
            continue

        # Valid format, check status and confirm
        if self._confirm_and_set_model(normalized_input, apply_selection=apply_selection):
            return normalized_input

    return None

def _manage_fallbacks(
    self,
    allowed_provider_ids: Optional[list[str] | set[str]] = None,
):
    """Interactively choose fallback models with multi-select."""
    normalized_allowed_provider_ids = [
        str(pid).strip()
        for pid in (allowed_provider_ids or [])
        if str(pid).strip()
    ]

    if not normalized_allowed_provider_ids:
        normalized_allowed_provider_ids = self._providers_with_saved_credentials()

    if not normalized_allowed_provider_ids:
        console.print("|  [yellow]No providers with saved credentials found.[/yellow]")
        console.print("|  [dim]Login provider first via Provider Login (API key/OAuth).[/dim]")
        return None

    primary, current_fallbacks = self._current_model_chain()
    all_models = [
        m for m in self.registry.list_models()
        if self._model_allowed_by_provider_credentials(m.id, normalized_allowed_provider_ids)
        and m.id != primary
    ]
    all_models.sort(key=lambda m: (not m.is_premium, m.id))

    if not all_models and not current_fallbacks:
        console.print("|  [yellow]No fallback candidates found for authenticated providers.[/yellow]")
        return None

    console.print("|")
    console.print("|  [bold]Select fallback models[/bold] (Space to toggle, Enter to confirm)")

    choices: list[questionary.Choice] = []
    known_ids = {m.id for m in all_models}
    for fallback_id in current_fallbacks:
        if fallback_id not in known_ids:
            choices.append(
                questionary.Choice(
                    f"{fallback_id} (custom)",
                    value=fallback_id,
                    checked=True,
                )
            )

    for model in all_models:
        label = model.id
        if model.name:
            label = f"{model.id} ({model.name})"
        choices.append(
            questionary.Choice(
                label,
                value=model.id,
                checked=model.id in current_fallbacks,
            )
        )

    selected = questionary.checkbox(
        "*  Choose fallback models",
        choices=choices,
        style=questionary.Style(
            [
                ("qmark", "fg:cyan bold"),
                ("question", "bold"),
                ("pointer", "fg:cyan bold noinherit"),
                ("text", "fg:white noinherit"),
                ("highlighted", "fg:cyan bold noinherit"),
                ("selected", "fg:cyan bold noinherit"),
                ("answer", "fg:white bold noinherit"),
            ]
        ),
    ).ask()

    if selected is None:
        console.print("|  [yellow]Cancelled[/yellow]")
        return None

    fallback_chain = [str(model_id).strip() for model_id in selected if str(model_id).strip()]
    self._set_model_chain(primary, fallback_chain)
    console.print(f"|  [green]OK Updated fallbacks ({len(fallback_chain)})[/green]")

    if fallback_chain:
        self._reorder_fallbacks()

    return fallback_chain


def _reorder_fallbacks(self):
    """Interactively reorder fallback chain using move up/down controls."""
    primary, fallbacks = self._current_model_chain()
    if len(fallbacks) <= 1:
        console.print("|  [dim]Need at least two fallback models to reorder.[/dim]")
        return None

    ordered = list(fallbacks)
    cursor = 0

    while True:
        console.print("|")
        console.print("|  [bold]Fallback order[/bold] (priority top -> bottom):")
        for idx, model_id in enumerate(ordered, start=1):
            marker = "=>" if idx - 1 == cursor else "  "
            console.print(f"|  {marker} {idx}. {model_id}")

        action = ClackUI.clack_select(
            "Reorder action",
            choices=[
                questionary.Choice("Move up", value="up"),
                questionary.Choice("Move down", value="down"),
                questionary.Choice("Select item", value="select"),
                questionary.Choice("Done", value="done"),
            ],
            default="done",
        )

        if action in {None, "done"}:
            break

        if action == "select":
            select_choices = [
                questionary.Choice(f"{idx + 1}. {model_id}", value=idx)
                for idx, model_id in enumerate(ordered)
            ]
            selected_index = ClackUI.clack_select(
                "Choose fallback to move",
                choices=select_choices,
                default=cursor,
            )
            if selected_index is not None:
                cursor = int(selected_index)
            continue

        if action == "up" and cursor > 0:
            ordered[cursor - 1], ordered[cursor] = ordered[cursor], ordered[cursor - 1]
            cursor -= 1
        elif action == "down" and cursor < len(ordered) - 1:
            ordered[cursor + 1], ordered[cursor] = ordered[cursor], ordered[cursor + 1]
            cursor += 1

    if ordered != fallbacks:
        self._set_model_chain(primary, ordered)
        console.print("|  [green]OK Fallback order updated[/green]")
    else:
        console.print("|  [dim]Fallback order unchanged.[/dim]")

    return ordered


def _confirm_and_set_model(self, model_id: str, apply_selection: bool = True) -> bool:
    """Confirm model selection and set if approved."""
    from kabot.providers.model_status import get_model_status, get_status_indicator

    status = get_model_status(model_id)
    indicator = get_status_indicator(status)

    console.print(f"|  {indicator} Model: {model_id}")
    console.print(f"|  Status: {status}")

    if status == "unsupported":
        console.print("|  [red]!  This provider is not supported by LiteLLM[/red]")
        console.print("|  [dim]The model may not work correctly[/dim]")
        if not Confirm.ask("|  Continue anyway", default=False):
            return False
    elif status == "catalog":
        console.print("|  [yellow]!  This model is in catalog but not verified[/yellow]")
        console.print("|  [dim]If you encounter issues, try a working model[/dim]")

    if apply_selection:
        current_primary, current_fallbacks = self._current_model_chain()
        if current_primary and model_id != current_primary:
            action = ClackUI.clack_select(
                "Model already configured. Choose action",
                choices=[
                    questionary.Choice("Set as primary", value="primary"),
                    questionary.Choice("Add as fallback", value="fallback"),
                    questionary.Choice("Cancel", value="cancel"),
                ],
                default="primary",
            )
            if action in {None, "cancel"}:
                console.print("|  [yellow]Cancelled[/yellow]")
                return False
            if action == "fallback":
                if model_id in current_fallbacks:
                    console.print(f"|  [dim]Model already exists in fallback chain: {model_id}[/dim]")
                else:
                    self._set_model_chain(current_primary, [*current_fallbacks, model_id])
                    console.print(f"|  [green]OK Added fallback: {model_id}[/green]")
                    self._reorder_fallbacks()
                return True

        self._set_model_chain(model_id, current_fallbacks)
        console.print(f"|  [green]OK Model set to {model_id}[/green]")
    else:
        console.print(f"|  [green]OK Selected model: {model_id}[/green]")
    return True

def _show_alias_help(self):
    """Show all available aliases."""
    from kabot.providers.registry import ModelRegistry

    registry = ModelRegistry()
    aliases = registry.get_all_aliases()

    # Group by provider
    grouped = {}
    for alias, model_id in aliases.items():
        provider = model_id.split("/")[0]
        if provider not in grouped:
            grouped[provider] = []
        grouped[provider].append((alias, model_id))

    console.print("|")
    console.print("|  [bold cyan]Available Model Aliases[/bold cyan]")
    console.print("|")

    for provider, items in sorted(grouped.items()):
        console.print(f"|  [bold]{provider.title()}:[/bold]")
        for alias, model_id in sorted(items):
            console.print(f"|    {alias:12} -> {model_id}")
        console.print("|")

    console.print("|  [dim]Press Enter to continue...[/dim]")
    input()

def _validate_groq_api_key_http(api_key: str) -> bool | None:
    """Validate Groq API key via OpenAI-compatible models endpoint without SDK dependency."""
    req = urllib_request.Request(
        url="https://api.groq.com/openai/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urllib_request.urlopen(req, timeout=8) as response:
            return int(getattr(response, "status", 0)) == 200
    except urllib_error.HTTPError as exc:
        if exc.code in {401, 403}:
            return False
        # Service-side or quota/transient errors shouldn't be treated as invalid key.
        return None
    except Exception:
        return None

def _validate_api_key(self, provider: str, api_key: str) -> bool | None:
    """Validate API key by making a test call."""
    if not api_key or api_key.strip() == "":
        return True  # Skip validation for empty keys

    try:
        if provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            client.models.list()
            return True
        elif provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        elif provider == "groq":
            try:
                import groq
                client = groq.Groq(api_key=api_key)
                client.models.list()
                return True
            except (ImportError, ModuleNotFoundError):
                return _validate_groq_api_key_http(api_key)
    except (ImportError, ModuleNotFoundError):
        return None
    except Exception as e:
        console.print(f"|  [red]Validation failed: {str(e)}[/red]")
        return False

    return True  # Default to valid for unknown providers

def _validate_provider_credentials(self, provider_id: str):
    """Validate provider credentials with user feedback and retry options."""
    import signal
    import time

    from rich.prompt import Confirm


    # Load current config to get the API key
    config = load_config()

    # Map provider IDs to config fields for credential lookup
    provider_mapping = {
        "openai": "openai",
        "anthropic": "anthropic",
        "google": "gemini",
        "groq": "groq",
        "kimi": "moonshot",
        "minimax": "minimax",
        "mistral": "mistral",
        "kilocode": "kilocode",
        "together": "together",
        "venice": "venice",
        "huggingface": "huggingface",
        "qianfan": "qianfan",
        "nvidia": "nvidia",
        "xai": "xai",
        "cerebras": "cerebras",
        "opencode": "opencode",
        "xiaomi": "xiaomi",
        "volcengine": "volcengine",
        "byteplus": "byteplus",
        "synthetic": "synthetic",
        "cloudflare-ai-gateway": "cloudflare_ai_gateway",
        "vercel-ai-gateway": "vercel_ai_gateway",
        "openrouter": "openrouter",
        "deepseek": "deepseek",
        "dashscope": "dashscope",
        "vllm": "vllm",
        "ollama": "vllm",
        "zhipu": "zhipu",
        "aihubmix": "aihubmix",
        "letta": "letta",
    }

    if provider_id not in provider_mapping:
        console.print(f"|  [yellow]Validation not supported for {provider_id}[/yellow]")
        return

    config_field = provider_mapping[provider_id]
    provider_config = getattr(config.providers, config_field, None)

    if not provider_config:
        console.print(f"|  [yellow]No configuration found for {provider_id}[/yellow]")
        return

    # Get credential from active profile or legacy field.
    credential_fields = ("api_key", "oauth_token", "setup_token")
    api_key = None
    if provider_config.active_profile and provider_config.profiles:
        active_profile = provider_config.profiles.get(provider_config.active_profile)
        if active_profile:
            for field in credential_fields:
                value = getattr(active_profile, field, None)
                if value:
                    api_key = value
                    break

    if not api_key:
        for field in credential_fields:
            value = getattr(provider_config, field, None)
            if value:
                api_key = value
                break

    if not api_key:
        console.print(f"|  [yellow]No API key found for {provider_id}[/yellow]")
        return

    console.print("|")
    console.print(f"|  [cyan]Validating {provider_id} API key...[/cyan]")

    # Validation with timeout and retry logic
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            # Set up timeout handler
            def timeout_handler(signum, frame):
                raise TimeoutError("Validation timed out")

            # Set timeout for validation (10 seconds)
            if hasattr(signal, 'SIGALRM'):  # Unix systems
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(10)

            # Perform validation
            is_valid = self._validate_api_key(provider_id, api_key)

            # Clear timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)

            if is_valid is True:
                console.print(f"|  [green]OK {provider_id} API key is valid[/green]")
                return
            elif is_valid is None:
                console.print(f"|  [yellow]! Validation skipped for {provider_id} (SDK/network unavailable).[/yellow]")
                if provider_id == "groq":
                    console.print("|  [dim]Tip: install SDK with `pip install groq` for deeper validation.[/dim]")
                return
            else:
                console.print(f"|  [red]X {provider_id} API key validation failed[/red]")
                break

        except TimeoutError:
            console.print(f"|  [yellow]! Validation timed out (attempt {attempt + 1}/{max_retries + 1})[/yellow]")
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)

        except ImportError as e:
            console.print(f"|  [yellow]! Cannot validate {provider_id}: Missing dependency ({str(e)})[/yellow]")
            console.print(f"|  [dim]Install with: pip install {provider_id}[/dim]")
            return

        except Exception as e:
            console.print(f"|  [red]X Validation error: {str(e)}[/red]")
            break

        # Ask if user wants to retry on timeout
        if attempt < max_retries:
            if not Confirm.ask("|  Retry validation", default=True):
                break
            console.print("|  [cyan]Retrying...[/cyan]")
            time.sleep(1)

    # Handle validation failure
    console.print("|")
    if Confirm.ask("|  Continue anyway (You can fix this later)", default=True):
        console.print("|  [yellow]! Continuing with potentially invalid key[/yellow]")
    else:
        console.print("|  [dim]You can reconfigure this provider later from the main menu[/dim]")

def bind_model_auth_sections(cls):
    cls._sync_provider_credentials_from_disk = _sync_provider_credentials_from_disk
    cls._provider_has_credentials = _provider_has_credentials
    cls._provider_config_key_for_auth = _provider_config_key_for_auth
    cls._provider_has_saved_credentials = _provider_has_saved_credentials
    cls._providers_with_saved_credentials = _providers_with_saved_credentials
    cls._model_allowed_by_provider_credentials = _model_allowed_by_provider_credentials
    cls._current_model_display = _current_model_display
    cls._current_model_chain = _current_model_chain
    cls._set_model_chain = _set_model_chain
    cls._provider_model_prefixes = _provider_model_prefixes
    cls._model_matches_provider = _model_matches_provider
    cls._normalize_scoped_manual_model_input = _normalize_scoped_manual_model_input
    cls._build_model_chain_from_provider_selections = _build_model_chain_from_provider_selections
    cls._apply_model_chain_from_provider_selections = _apply_model_chain_from_provider_selections
    cls._apply_post_login_defaults = _apply_post_login_defaults
    cls._recommended_auto_model_chain = _recommended_auto_model_chain
    cls._apply_auto_default_model_chain = _apply_auto_default_model_chain
    cls._show_auto_model_chain_summary = _show_auto_model_chain_summary
    cls._configure_model = _configure_model
    cls._configure_memory = _configure_memory
    cls._model_picker = _model_picker
    cls._model_browser = _model_browser
    cls._manual_model_entry = _manual_model_entry
    cls._manage_fallbacks = _manage_fallbacks
    cls._reorder_fallbacks = _reorder_fallbacks
    cls._confirm_and_set_model = _confirm_and_set_model
    cls._show_alias_help = _show_alias_help
    cls._validate_api_key = _validate_api_key
    cls._validate_provider_credentials = _validate_provider_credentials
    return cls
