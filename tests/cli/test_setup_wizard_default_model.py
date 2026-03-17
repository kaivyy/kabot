import builtins
import json
import shutil
from pathlib import Path

from kabot.cli.setup_wizard import SetupWizard
from kabot.config.schema import AgentModelConfig, AuthProfile
from kabot.providers.models import ModelMetadata


def test_apply_post_login_defaults_does_not_inject_hardcoded_models():
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = "openai/gpt-4o"
    wizard.config.providers.openai_codex.profiles["default"] = AuthProfile(
        name="default",
        oauth_token="tok",
        token_type="oauth",
    )
    wizard.config.providers.openai_codex.active_profile = "default"
    wizard.config.providers.groq.api_key = "groq-key"

    changed = wizard._apply_post_login_defaults("openai")

    assert changed is False
    assert wizard.config.agents.defaults.model == "openai/gpt-4o"


def test_provider_model_prefixes_include_expected_variants():
    wizard = SetupWizard()

    openai_prefixes = wizard._provider_model_prefixes("openai")
    kimi_prefixes = wizard._provider_model_prefixes("kimi")
    ollama_prefixes = wizard._provider_model_prefixes("ollama")

    assert "openai" in openai_prefixes
    assert "openai-codex" in openai_prefixes
    assert "moonshot" in kimi_prefixes
    assert "kimi-coding" in kimi_prefixes
    assert "ollama" in ollama_prefixes
    assert "vllm" in ollama_prefixes


def test_build_model_chain_from_provider_selections_respects_user_order():
    wizard = SetupWizard()

    provider_models = {
        "openai": "openai/gpt-4o",
        "kimi": "moonshot/kimi-k2.5",
        "groq": "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    }
    provider_order = ["openai", "kimi", "groq"]

    chain = wizard._build_model_chain_from_provider_selections(provider_models, provider_order)

    assert chain == [
        "openai/gpt-4o",
        "moonshot/kimi-k2.5",
        "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    ]


def test_build_model_chain_from_provider_selections_deduplicates_models():
    wizard = SetupWizard()

    provider_models = {
        "openai": "openai/gpt-4o",
        "openrouter": "openai/gpt-4o",
        "groq": "groq/llama3-70b-8192",
    }
    provider_order = ["openai", "openrouter", "groq"]

    chain = wizard._build_model_chain_from_provider_selections(provider_models, provider_order)

    assert chain == [
        "openai/gpt-4o",
        "groq/llama3-70b-8192",
    ]


def test_apply_model_chain_from_provider_selections_sets_primary_and_fallbacks():
    wizard = SetupWizard()

    changed = wizard._apply_model_chain_from_provider_selections(
        provider_models={
            "openai": "openai/gpt-4o",
            "kimi": "moonshot/kimi-k2.5",
        },
        provider_order=["openai", "kimi"],
    )

    assert changed is True
    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.primary == "openai/gpt-4o"
    assert wizard.config.agents.defaults.model.fallbacks == ["moonshot/kimi-k2.5"]


def test_apply_model_chain_from_provider_selections_keeps_existing_when_same():
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = AgentModelConfig(
        primary="openai/gpt-4o",
        fallbacks=["moonshot/kimi-k2.5"],
    )

    changed = wizard._apply_model_chain_from_provider_selections(
        provider_models={
            "openai": "openai/gpt-4o",
            "kimi": "moonshot/kimi-k2.5",
        },
        provider_order=["openai", "kimi"],
    )

    assert changed is False


def test_provider_has_credentials_accepts_setup_token():
    wizard = SetupWizard()
    wizard.config.providers.anthropic.profiles["default"] = AuthProfile(
        name="default",
        setup_token="sk-ant-oat01-example",
        token_type="token",
    )
    wizard.config.providers.anthropic.active_profile = "default"

    assert wizard._provider_has_credentials(wizard.config.providers.anthropic) is True


def test_provider_has_saved_credentials_uses_provider_mapping():
    wizard = SetupWizard()
    wizard.config.providers.groq.api_key = "gsk-test"
    wizard.config.providers.moonshot.profiles["default"] = AuthProfile(
        name="default",
        api_key="kimi-test",
        token_type="api_key",
    )
    wizard.config.providers.moonshot.active_profile = "default"
    wizard.config.providers.vllm.api_key = "ollama"

    assert wizard._provider_has_saved_credentials("groq") is True
    assert wizard._provider_has_saved_credentials("kimi") is True
    assert wizard._provider_has_saved_credentials("ollama") is True
    assert wizard._provider_has_saved_credentials("unknown-provider") is False


def test_provider_has_saved_credentials_openai_detects_openai_codex_oauth():
    wizard = SetupWizard()
    wizard.config.providers.openai_codex.profiles["default"] = AuthProfile(
        name="default",
        oauth_token="tok-openai-codex",
        token_type="oauth",
    )
    wizard.config.providers.openai_codex.active_profile = "default"

    assert wizard._provider_has_saved_credentials("openai") is True


def test_provider_mapping_covers_all_auth_providers():
    from kabot.auth.menu import AUTH_PROVIDERS

    wizard = SetupWizard()
    missing_config_map = [
        provider_id
        for provider_id in AUTH_PROVIDERS
        if wizard._provider_config_key_for_auth(provider_id) is None
    ]
    missing_prefix_map = [
        provider_id
        for provider_id in AUTH_PROVIDERS
        if not wizard._provider_model_prefixes(provider_id)
    ]

    assert missing_config_map == []
    assert missing_prefix_map == []


def test_current_model_display_uses_primary_for_agent_model_config():
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = AgentModelConfig(
        primary="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        fallbacks=[],
    )
    assert wizard._current_model_display() == "groq/meta-llama/llama-4-scout-17b-16e-instruct"


def test_current_model_chain_and_set_model_chain_normalize_state():
    wizard = SetupWizard()

    primary, fallbacks = wizard._current_model_chain()
    assert primary
    assert fallbacks == []

    wizard._set_model_chain(
        "openai/gpt-4o",
        ["groq/llama3-70b-8192", "openai/gpt-4o", "groq/llama3-70b-8192", "moonshot/kimi-k2.5"],
    )

    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.primary == "openai/gpt-4o"
    assert wizard.config.agents.defaults.model.fallbacks == [
        "groq/llama3-70b-8192",
        "moonshot/kimi-k2.5",
    ]


def test_confirm_and_set_model_can_add_model_as_fallback(monkeypatch):
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = AgentModelConfig(
        primary="openai/gpt-4o",
        fallbacks=["groq/llama3-70b-8192"],
    )

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.ClackUI.clack_select",
        lambda *args, **kwargs: "fallback",
    )
    monkeypatch.setattr(wizard, "_reorder_fallbacks", lambda: None)

    changed = wizard._confirm_and_set_model("moonshot/kimi-k2.5", apply_selection=True)

    assert changed is True
    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.primary == "openai/gpt-4o"
    assert wizard.config.agents.defaults.model.fallbacks == [
        "groq/llama3-70b-8192",
        "moonshot/kimi-k2.5",
    ]


def test_confirm_and_set_model_can_promote_model_to_primary(monkeypatch):
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = AgentModelConfig(
        primary="openai/gpt-4o",
        fallbacks=["groq/llama3-70b-8192"],
    )

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.ClackUI.clack_select",
        lambda *args, **kwargs: "primary",
    )

    changed = wizard._confirm_and_set_model("moonshot/kimi-k2.5", apply_selection=True)

    assert changed is True
    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.primary == "moonshot/kimi-k2.5"
    assert wizard.config.agents.defaults.model.fallbacks == ["groq/llama3-70b-8192"]


def test_confirm_and_set_model_cancel_keeps_existing_chain(monkeypatch):
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = AgentModelConfig(
        primary="openai/gpt-4o",
        fallbacks=["groq/llama3-70b-8192"],
    )

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.ClackUI.clack_select",
        lambda *args, **kwargs: "cancel",
    )

    changed = wizard._confirm_and_set_model("moonshot/kimi-k2.5", apply_selection=True)

    assert changed is False
    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.primary == "openai/gpt-4o"
    assert wizard.config.agents.defaults.model.fallbacks == ["groq/llama3-70b-8192"]


def test_reorder_fallbacks_moves_items_with_up_and_down(monkeypatch):
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = AgentModelConfig(
        primary="openai/gpt-4o",
        fallbacks=["a/model", "b/model", "c/model"],
    )

    actions = iter(["down", "down", "up", "done"])

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.ClackUI.clack_select",
        lambda *args, **kwargs: next(actions),
    )

    reordered = wizard._reorder_fallbacks()

    assert reordered == ["b/model", "a/model", "c/model"]
    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.fallbacks == ["b/model", "a/model", "c/model"]


def test_manage_fallbacks_uses_checkbox_selection_and_triggers_reorder(monkeypatch):
    wizard = SetupWizard()
    wizard.config.agents.defaults.model = AgentModelConfig(
        primary="openai/gpt-4o",
        fallbacks=["groq/llama3-70b-8192"],
    )
    wizard.config.providers.openai.api_key = "sk-openai"

    sample_models = [
        ModelMetadata(id="openai/gpt-4o", name="GPT-4o", provider="openai"),
        ModelMetadata(id="openai/gpt-5.2-codex", name="GPT-5.2 Codex", provider="openai"),
        ModelMetadata(id="groq/llama3-70b-8192", name="Llama", provider="groq"),
    ]
    monkeypatch.setattr(wizard.registry, "list_models", lambda: sample_models)

    class _DummyCheckbox:
        def ask(self):
            return ["openai/gpt-5.2-codex", "groq/llama3-70b-8192"]

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.questionary.checkbox",
        lambda *args, **kwargs: _DummyCheckbox(),
    )

    reordered_calls: list[bool] = []
    monkeypatch.setattr(wizard, "_reorder_fallbacks", lambda: reordered_calls.append(True))

    result = wizard._manage_fallbacks(allowed_provider_ids=["openai", "groq"])

    assert result == ["openai/gpt-5.2-codex", "groq/llama3-70b-8192"]
    assert reordered_calls == [True]
    assert isinstance(wizard.config.agents.defaults.model, AgentModelConfig)
    assert wizard.config.agents.defaults.model.primary == "openai/gpt-4o"
    assert wizard.config.agents.defaults.model.fallbacks == [
        "openai/gpt-5.2-codex",
        "groq/llama3-70b-8192",
    ]


def test_configure_model_uses_saved_credentials_when_selected(monkeypatch):
    wizard = SetupWizard()
    wizard.config.providers.groq.api_key = "gsk-test"

    state = {"user_selections": {}}

    class _DummyAuthManager:
        def __init__(self):
            self.called = False

        def login(self, provider_id):
            self.called = True
            return True

    manager = _DummyAuthManager()

    selections = iter(["login", "groq", "use_saved", "back"])

    def _fake_select(_message, choices=None, default=None):
        return next(selections)

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.ClackUI.clack_select",
        _fake_select,
    )
    monkeypatch.setattr("kabot.auth.manager.AuthManager", lambda: manager)
    monkeypatch.setattr(
        "kabot.auth.menu.get_auth_choices",
        lambda: [{"name": "Groq - Llama 4 Scout", "value": "groq"}],
    )
    monkeypatch.setattr(wizard, "_load_setup_state", lambda: state)
    monkeypatch.setattr(wizard, "_write_setup_state", lambda payload: state.update(payload))
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(wizard, "_sync_provider_credentials_from_disk", lambda: None)
    monkeypatch.setattr(
        wizard,
        "_validate_provider_credentials",
        lambda provider_id: (_ for _ in ()).throw(AssertionError("validation should be skipped")),
    )
    monkeypatch.setattr(
        wizard,
        "_model_browser",
        lambda provider_id, apply_selection=False, preferred_model=None, prefer_first_provider_model=False: "groq/llama3-70b-8192",
    )

    wizard._configure_model()

    assert manager.called is False
    primary, fallbacks = wizard._current_model_chain()
    assert primary == "groq/llama3-70b-8192"
    assert fallbacks == []
    assert state["user_selections"]["provider_models"]["groq"] == "groq/llama3-70b-8192"


def test_configure_model_allows_relogin_when_credentials_exist(monkeypatch):
    wizard = SetupWizard()
    wizard.config.providers.openai_codex.profiles["default"] = AuthProfile(
        name="default",
        oauth_token="tok-openai-codex",
        token_type="oauth",
    )
    wizard.config.providers.openai_codex.active_profile = "default"

    state = {"user_selections": {}}

    class _DummyAuthManager:
        def __init__(self):
            self.called = False

        def login(self, provider_id):
            self.called = True
            return True

    manager = _DummyAuthManager()

    selections = iter(["login", "openai", "relogin", "back"])

    def _fake_select(_message, choices=None, default=None):
        return next(selections)

    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.ClackUI.clack_select",
        _fake_select,
    )
    monkeypatch.setattr("kabot.auth.manager.AuthManager", lambda: manager)
    monkeypatch.setattr(
        "kabot.auth.menu.get_auth_choices",
        lambda: [{"name": "OpenAI - GPT-4o, o1-preview, etc.", "value": "openai"}],
    )
    monkeypatch.setattr(wizard, "_load_setup_state", lambda: state)
    monkeypatch.setattr(wizard, "_write_setup_state", lambda payload: state.update(payload))
    monkeypatch.setattr(wizard, "_save_setup_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(wizard, "_sync_provider_credentials_from_disk", lambda: None)
    monkeypatch.setattr(wizard, "_validate_provider_credentials", lambda provider_id: None)
    monkeypatch.setattr(
        wizard,
        "_model_browser",
        lambda provider_id, apply_selection=False, preferred_model=None, prefer_first_provider_model=False: "openai/gpt-4o",
    )

    wizard._configure_model()

    assert manager.called is True
    primary, fallbacks = wizard._current_model_chain()
    assert primary == "openai/gpt-4o"
    assert fallbacks == []
    assert state["user_selections"]["provider_models"]["openai"] == "openai/gpt-4o"


def test_model_browser_prefers_first_provider_model_on_login_flow(monkeypatch):
    wizard = SetupWizard()

    sample_models = [
        ModelMetadata(id="groq/llama3-70b-8192", name="Llama 3 70B", provider="groq"),
        ModelMetadata(id="groq/mixtral-8x7b-32768", name="Mixtral", provider="groq"),
    ]
    monkeypatch.setattr(wizard.registry, "list_models", lambda: sample_models)
    monkeypatch.setattr(wizard.registry, "get_providers", lambda: {"groq": 2})

    captured: dict[str, object] = {}

    def _fake_select(message, choices=None, default=None):
        captured["default"] = default
        return None

    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.ClackUI.clack_select", _fake_select)

    result = wizard._model_browser(
        provider_id="groq",
        apply_selection=False,
        prefer_first_provider_model=True,
    )

    assert result is None
    assert captured["default"] == "groq/llama3-70b-8192"


def test_model_browser_groups_verified_and_catalog_sections(monkeypatch):
    wizard = SetupWizard()

    sample_models = [
        ModelMetadata(id="openai/gpt-4o", name="GPT-4o", provider="openai"),
        ModelMetadata(id="openai/gpt-5.1-codex", name="GPT-5.1 Codex", provider="openai"),
    ]
    monkeypatch.setattr(wizard.registry, "list_models", lambda: sample_models)
    monkeypatch.setattr(wizard.registry, "get_providers", lambda: {"openai": 2})

    captured: dict[str, object] = {}

    def _fake_select(message, choices=None, default=None):
        captured["choices"] = choices
        return None

    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.ClackUI.clack_select", _fake_select)

    result = wizard._model_browser(provider_id="openai", apply_selection=False)

    assert result is None
    choices = captured["choices"]
    separator_titles = [
        getattr(c, "title", "")
        for c in choices
        if c.__class__.__name__ == "Separator"
    ]
    assert any("Verified Models" in title for title in separator_titles)
    assert any("Catalog Models" in title for title in separator_titles)

    model_values = [getattr(c, "value", None) for c in choices if isinstance(getattr(c, "value", None), str)]
    assert model_values.index("openai/gpt-4o") < model_values.index("openai/gpt-5.1-codex")


def test_model_picker_shows_only_aliases_from_authenticated_providers(monkeypatch):
    wizard = SetupWizard()
    wizard.config.providers.openai.api_key = "sk-openai"

    captured: dict[str, object] = {}

    def _fake_select(message, choices=None, default=None):
        captured["choices"] = choices
        return None

    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.ClackUI.clack_select", _fake_select)

    wizard._model_picker()

    values = [getattr(c, "value", None) for c in captured["choices"] if hasattr(c, "value")]
    assert "alias:codex" in values
    assert "alias:gpt4o" in values
    assert "alias:sonnet" not in values
    assert "alias:gemini" not in values


def test_model_picker_warns_and_exits_when_no_authenticated_providers(monkeypatch):
    wizard = SetupWizard()
    messages: list[str] = []

    monkeypatch.setattr(wizard, "_providers_with_saved_credentials", lambda: [])
    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.console.print", lambda msg: messages.append(str(msg)))
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth.ClackUI.clack_select",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("select should not be called")),
    )

    result = wizard._model_picker()

    assert result is None
    assert any("No providers with saved credentials" in msg for msg in messages)


def test_model_browser_all_mode_filters_to_authenticated_provider_scope(monkeypatch):
    wizard = SetupWizard()

    sample_models = [
        ModelMetadata(id="openai/gpt-4o", name="GPT-4o", provider="openai"),
        ModelMetadata(id="anthropic/claude-3-5-sonnet-20241022", name="Claude", provider="anthropic"),
    ]
    monkeypatch.setattr(wizard.registry, "list_models", lambda: sample_models)
    monkeypatch.setattr(wizard.registry, "get_providers", lambda: {"openai": 1, "anthropic": 1})

    captured: dict[str, object] = {}
    calls = iter(["all", None])

    def _fake_select(message, choices=None, default=None):
        if "Select default model" in message:
            captured["choices"] = choices
        return next(calls)

    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.ClackUI.clack_select", _fake_select)

    result = wizard._model_browser(
        provider_id=None,
        apply_selection=False,
        allowed_provider_ids={"openai"},
    )

    assert result is None
    model_values = [getattr(c, "value", None) for c in captured["choices"] if hasattr(c, "value")]
    assert "openai/gpt-4o" in model_values
    assert "anthropic/claude-3-5-sonnet-20241022" not in model_values


def test_manual_model_entry_rejects_provider_without_saved_credentials(monkeypatch):
    wizard = SetupWizard()

    inputs = iter(["anthropic/claude-3-5-sonnet-20241022", "back"])
    messages: list[str] = []

    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.Prompt.ask", lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.console.print", lambda msg: messages.append(str(msg)))
    monkeypatch.setattr(
        wizard,
        "_confirm_and_set_model",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not confirm blocked provider")),
    )

    result = wizard._manual_model_entry(
        provider_id=None,
        apply_selection=False,
        allowed_provider_ids={"openai"},
    )

    assert result is None
    assert any("saved credentials" in msg.lower() for msg in messages)


def test_manual_model_entry_provider_scope_autoprefixes_nested_model(monkeypatch):
    wizard = SetupWizard()

    inputs = iter(["arcee-ai/trinity-large-preview:free"])
    selected: list[str] = []

    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.Prompt.ask", lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr("kabot.cli.wizard.sections.model_auth.console.print", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        wizard,
        "_confirm_and_set_model",
        lambda model_id, apply_selection=False: selected.append(model_id) or True,
    )

    result = wizard._manual_model_entry(
        provider_id="openrouter",
        apply_selection=False,
        allowed_provider_ids={"openrouter"},
    )

    assert result == "openrouter/arcee-ai/trinity-large-preview:free"
    assert selected == ["openrouter/arcee-ai/trinity-large-preview:free"]


def test_validate_api_key_returns_none_when_provider_dependency_missing(monkeypatch):
    wizard = SetupWizard()
    real_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "groq":
            raise ModuleNotFoundError("No module named 'groq'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.setattr(
        "kabot.cli.wizard.sections.model_auth._validate_groq_api_key_http",
        lambda _api_key: None,
    )

    result = wizard._validate_api_key("groq", "gsk-test")

    assert result is None


def test_sync_provider_credentials_from_disk_preserves_unsaved_config(monkeypatch):
    wizard = SetupWizard()
    wizard.config.agents.defaults.workspace = "~/my-local-workspace"

    disk_config = wizard.config.model_copy(deep=True)
    disk_config.providers.openai_codex.profiles["default"] = AuthProfile(
        name="default",
        oauth_token="tok",
        token_type="oauth",
    )
    disk_config.providers.openai_codex.active_profile = "default"

    monkeypatch.setattr("kabot.cli.setup_wizard.load_config", lambda: disk_config)

    wizard._sync_provider_credentials_from_disk()

    assert wizard.config.agents.defaults.workspace == "~/my-local-workspace"
    assert wizard.config.providers.openai_codex.profiles["default"].oauth_token == "tok"


def test_save_setup_state_serializes_agent_model_config(monkeypatch):
    test_home = Path.cwd() / ".tmp-test-home-setup-wizard"
    if test_home.exists():
        shutil.rmtree(test_home)
    test_home.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: test_home)

    wizard = SetupWizard()
    model_config = AgentModelConfig(
        primary="openai-codex/gpt-5.3-codex",
        fallbacks=["openai/gpt-5.2-codex"],
    )

    wizard._save_setup_state("auth", completed=True, default_model=model_config)

    state_file = test_home / ".kabot" / "setup-state.json"
    state = json.loads(state_file.read_text())

    assert state["sections"]["auth"]["default_model"]["primary"] == "openai-codex/gpt-5.3-codex"
    assert state["sections"]["auth"]["default_model"]["fallbacks"] == ["openai/gpt-5.2-codex"]
    shutil.rmtree(test_home, ignore_errors=True)
