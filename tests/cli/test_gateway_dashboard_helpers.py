from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace

import pytest


def test_build_dashboard_config_summary_exposes_safe_fields_only(monkeypatch):
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    cfg.gateway.host = "127.0.0.1"
    cfg.gateway.port = 18790
    cfg.gateway.bind_mode = "local"
    cfg.gateway.auth_token = "secret-token"
    cfg.runtime.performance.token_mode = "hemat"
    cfg.tools.web.search.provider = "brave"

    def _fake_provider_models():
        return {
            "openrouter": ["openrouter/auto", "openrouter/moonshotai/kimi-k2.5"],
            "groq": ["groq/llama3-70b-8192"],
        }

    monkeypatch.setattr(
        commands,
        "_list_provider_models_for_dashboard",
        _fake_provider_models,
    )
    summary = commands._build_dashboard_config_summary(cfg)

    assert summary["gateway"]["host"] == "127.0.0.1"
    assert summary["gateway"]["port"] == 18790
    assert summary["gateway"]["bind_mode"] == "local"
    assert summary["gateway"]["auth_token_configured"] is True
    assert summary["runtime"]["performance"]["token_mode"] == "hemat"
    assert summary["tools"]["web"]["search_provider"] == "brave"
    assert "openrouter" in summary["providers"]["available"]
    assert summary["providers"]["models_by_provider"]["openrouter"] == [
        "openrouter/auto",
        "openrouter/moonshotai/kimi-k2.5",
    ]


def test_build_dashboard_config_summary_exposes_model_chain():
    from kabot.cli import commands
    from kabot.config.schema import AgentModelConfig, Config

    cfg = Config()
    cfg.agents.defaults.model = AgentModelConfig(
        primary="openai-codex/gpt-5.3-codex",
        fallbacks=["openai/gpt-4o-mini", "groq/llama-3.3-70b"],
    )

    summary = commands._build_dashboard_config_summary(cfg)

    assert summary["runtime"]["model"]["primary"] == "openai-codex/gpt-5.3-codex"
    assert summary["runtime"]["model"]["fallbacks"] == [
        "openai/gpt-4o-mini",
        "groq/llama-3.3-70b",
    ]
    assert summary["runtime"]["model"]["chain"] == [
        "openai-codex/gpt-5.3-codex",
        "openai/gpt-4o-mini",
        "groq/llama-3.3-70b",
    ]


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_sets_token_mode_and_saves():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    cfg.runtime.performance.token_mode = "boros"
    saved = {"called": False}

    def _fake_save(updated_cfg):
        saved["called"] = True
        saved["mode"] = updated_cfg.runtime.performance.token_mode

    result = await commands._gateway_dashboard_control_action(
        action="config.set_token_mode",
        args={"token_mode": "hemat"},
        config=cfg,
        save_config_fn=_fake_save,
        agent=SimpleNamespace(process_direct=None),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=SimpleNamespace(get_status=lambda: {}),
    )

    assert result["ok"] is True
    assert result["token_mode"] == "hemat"
    assert cfg.runtime.performance.token_mode == "hemat"
    assert saved["called"] is True
    assert saved["mode"] == "hemat"


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_chat_send_uses_agent_process_direct():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    called: dict[str, str] = {}

    async def _fake_process_direct(
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        model_override: str | None = None,
        fallback_overrides: list[str] | None = None,
    ):
        called["content"] = content
        called["session_key"] = session_key
        called["channel"] = channel
        called["chat_id"] = chat_id
        called["model_override"] = model_override
        called["fallback_overrides"] = fallback_overrides
        return "runtime reply"

    result = await commands._gateway_dashboard_control_action(
        action="chat.send",
        args={
            "prompt": "hello",
            "session_key": "dashboard:web",
            "provider": "openrouter",
            "model": "auto",
            "fallbacks": "groq/llama3-70b-8192,openai/gpt-4o-mini",
        },
        config=cfg,
        save_config_fn=lambda _cfg: None,
        agent=SimpleNamespace(process_direct=_fake_process_direct),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=SimpleNamespace(get_status=lambda: {}),
    )

    assert result["ok"] is True
    assert result["content"] == "runtime reply"
    assert called["content"] == "hello"
    assert called["session_key"] == "dashboard:web"
    assert called["channel"] == "dashboard"
    assert called["chat_id"] == "dashboard"
    assert called["model_override"] == "openrouter/auto"
    assert called["fallback_overrides"] == ["groq/llama3-70b-8192", "openai/gpt-4o-mini"]


def test_gateway_dashboard_chat_history_provider_reads_session_messages():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    session = SimpleNamespace(
        messages=[
            {"role": "user", "content": "hello", "timestamp": "t1"},
            {"role": "assistant", "content": "hi", "timestamp": "t2"},
        ]
    )
    session_manager = SimpleNamespace(get_or_create=lambda _key: session)

    items = commands._gateway_dashboard_chat_history_provider(
        session_manager=session_manager,
        session_key="dashboard:web",
        limit=30,
        config=cfg,
    )

    assert items == session.messages


def test_gateway_dashboard_chat_history_provider_preserves_status_metadata():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    session = SimpleNamespace(
        messages=[
            {
                "role": "assistant",
                "content": "Plan approved.",
                "timestamp": "t1",
                "metadata": {"type": "status_update", "phase": "approved"},
            }
        ]
    )
    session_manager = SimpleNamespace(get_or_create=lambda _key: session)

    items = commands._gateway_dashboard_chat_history_provider(
        session_manager=session_manager,
        session_key="dashboard:web",
        limit=30,
        config=cfg,
    )

    assert items[0]["metadata"]["type"] == "status_update"
    assert items[0]["metadata"]["phase"] == "approved"


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_sessions_clear_saves_session():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    saved = {"called": False}
    session = SimpleNamespace(
        messages=[{"role": "user", "content": "hello"}],
        clear=lambda: None,
    )
    session.clear = lambda: session.messages.clear()  # type: ignore[method-assign]
    session_manager = SimpleNamespace(
        get_or_create=lambda _key: session,
        save=lambda _session: saved.update({"called": True}),
        list_sessions=lambda: [],
    )

    result = await commands._gateway_dashboard_control_action(
        action="sessions.clear",
        args={"session_key": "telegram:123"},
        config=cfg,
        save_config_fn=lambda _cfg: None,
        agent=SimpleNamespace(process_direct=None),
        session_manager=session_manager,
        channels=SimpleNamespace(get_status=lambda: {}),
    )

    assert result["ok"] is True
    assert result["session_key"] == "telegram:123"
    assert saved["called"] is True
    assert session.messages == []


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_sessions_delete_returns_404_when_missing():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    session_manager = SimpleNamespace(
        delete=lambda _key: False,
        list_sessions=lambda: [],
    )

    result = await commands._gateway_dashboard_control_action(
        action="sessions.delete",
        args={"session_key": "telegram:missing"},
        config=cfg,
        save_config_fn=lambda _cfg: None,
        agent=SimpleNamespace(process_direct=None),
        session_manager=session_manager,
        channels=SimpleNamespace(get_status=lambda: {}),
    )

    assert result["ok"] is False
    assert result["status_code"] == 404
    assert result["error"] == "session_not_found"


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_nodes_stop_calls_channel_stop():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    state = {"stopped": False}

    class _FakeChannel:
        is_running = True

        async def stop(self):
            state["stopped"] = True

    channels = SimpleNamespace(
        get_status=lambda: {},
        get_channel=lambda _name: _FakeChannel(),
    )

    result = await commands._gateway_dashboard_control_action(
        action="nodes.stop",
        args={"node_id": "channel:telegram"},
        config=cfg,
        save_config_fn=lambda _cfg: None,
        agent=SimpleNamespace(process_direct=None),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=channels,
    )

    assert result["ok"] is True
    assert result["node_id"] == "channel:telegram"
    assert result["state"] == "stopped"
    assert state["stopped"] is True


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_nodes_start_returns_404_for_unknown_channel():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    channels = SimpleNamespace(
        get_status=lambda: {},
        get_channel=lambda _name: None,
    )

    result = await commands._gateway_dashboard_control_action(
        action="nodes.start",
        args={"node_id": "channel:missing"},
        config=cfg,
        save_config_fn=lambda _cfg: None,
        agent=SimpleNamespace(process_direct=None),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=channels,
    )

    assert result["ok"] is False
    assert result["status_code"] == 404
    assert result["error"] == "node_not_found"


def test_build_dashboard_status_payload_includes_enriched_monitoring_data(monkeypatch, tmp_path):
    from kabot.agent.subagent_registry import SubagentRunRecord
    from kabot.cli import commands
    from kabot.config.schema import Config
    from kabot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    with open(sessions_dir / "demo.jsonl", "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "role": "assistant",
                    "timestamp": "2026-03-07T10:00:00",
                    "model": "gpt-4o-mini",
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
                }
            )
            + "\n"
        )

    class _FakeSkillsLoader:
        def __init__(self, *args, **kwargs):
            pass

        def list_skills(self, filter_unavailable: bool = True):
            assert filter_unavailable is False
            return [
                {
                    "name": "demo-skill",
                    "skill_key": "demo-skill",
                    "eligible": True,
                    "disabled": False,
                    "description": "Demo skill",
                    "primaryEnv": "DEMO_SKILL_API_KEY",
                    "missing": {"env": [], "bins": [], "os": []},
                }
            ]

    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _FakeSkillsLoader)

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=0,
            stdout="abc123|feat: dashboard|2026-03-07T09:00:00+00:00|Arvy\n",
            stderr="",
        )

    monkeypatch.setattr(commands.subprocess, "run", _fake_run)

    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)

    cron_job = CronJob(
        id="job-1",
        name="Daily ping",
        schedule=CronSchedule(kind="every", every_ms=60000),
        payload=CronPayload(message="ping gateway", deliver=True, channel="telegram", to="123"),
        state=CronJobState(
            next_run_at_ms=1709802000000,
            last_run_at_ms=1709801940000,
            last_status="error",
            last_error="boom",
            run_history=[
                {
                    "run_at_ms": 1709801940000,
                    "status": "error",
                    "error": "boom",
                    "duration_ms": 321,
                }
            ],
        ),
        created_at_ms=1709801000000,
        updated_at_ms=1709801940000,
    )

    payload = commands._build_dashboard_status_payload(
        gateway_started_at=1709800000,
        runtime_model="gpt-4o-mini",
        runtime_fallbacks=["openai-codex/gpt-5.3-codex"],
        runtime_host="127.0.0.1",
        runtime_port=18790,
        tailscale_mode="off",
        session_manager=SimpleNamespace(
            sessions_dir=sessions_dir,
            list_sessions=lambda: ["telegram:123"],
        ),
        channels=SimpleNamespace(
            enabled_channels=["telegram"],
            get_status=lambda: {"telegram": {"running": True, "connected": True}},
        ),
        cron=SimpleNamespace(
            status=lambda: {"enabled": True, "jobs": 1},
            list_jobs=lambda include_disabled=False: [cron_job],
            get_run_history=lambda job_id: list(cron_job.state.run_history),
        ),
        config=cfg,
        agent=SimpleNamespace(
            subagents=SimpleNamespace(
                registry=SimpleNamespace(
                    list_all=lambda: [
                        SubagentRunRecord(
                            run_id="run-1",
                            task="Investigate failed webhook",
                            label="Failure triage",
                            parent_session_key="telegram:123",
                            origin_channel="telegram",
                            origin_chat_id="123",
                            status="failed",
                            created_at=1709801500.0,
                            completed_at=1709801600.0,
                            result="Timed out",
                            error="timeout",
                        )
                    ]
                )
            )
        ),
    )

    assert payload["status"] == "running"
    assert payload["costs"]["today"] >= 0
    assert payload["token_usage"]["total"] == 1500
    assert payload["model_usage"]["gpt-4o-mini"] == 1500
    assert payload["runtime_models"] == ["gpt-4o-mini", "openai-codex/gpt-5.3-codex"]
    assert payload["costs"]["by_model"]["openai-codex/gpt-5.3-codex"] == 0.0
    assert payload["usage_windows"]["7d"]["model_usage"]["gpt-4o-mini"] == 1500
    assert payload["usage_windows"]["7d"]["model_usage"]["openai-codex/gpt-5.3-codex"] == 0
    assert payload["usage_windows"]["all"]["costs"]["by_model"]["openai-codex/gpt-5.3-codex"] == 0.0
    assert payload["cost_history"][0]["tokens"] == 1500
    assert payload["cron_jobs_list"][0]["name"] == "Daily ping"
    assert payload["cron_jobs_list"][0]["last_status"] == "error"
    assert payload["skills"][0]["name"] == "demo-skill"
    assert payload["subagent_activity"][0]["status"] == "failed"
    assert payload["git_log"][0]["sha"] == "abc123"


def test_build_dashboard_status_payload_includes_recent_turn_continuity_metadata(tmp_path):
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    recent_session = SimpleNamespace(
        metadata={
            "last_turn_category": "chat",
            "pending_interrupt_count": 2,
            "last_completion_evidence": {
                "executed_tools": ["weather"],
                "artifact_paths": [],
                "artifact_verified": False,
                "delivery_verified": False,
            },
        },
        messages=[
            {
                "role": "assistant",
                "content": "Untuk bepergian di Cilacap, pakai pakaian ringan.",
                "timestamp": "2026-03-11T10:00:00",
                "metadata": {
                    "continuity_source": "answer_reference",
                    "route_profile": "CHAT",
                    "route_complex": False,
                    "required_tool": "weather",
                    "required_tool_query": "cek suhu cilacap sekarang",
                },
            }
        ]
    )

    payload = commands._build_dashboard_status_payload(
        gateway_started_at=1709800000,
        runtime_model="gpt-4o-mini",
        runtime_fallbacks=[],
        runtime_host="127.0.0.1",
        runtime_port=18790,
        tailscale_mode="off",
        session_manager=SimpleNamespace(
            sessions_dir=tmp_path,
            list_sessions=lambda: [
                {
                    "key": "telegram:123",
                    "updated_at": "2026-03-11T10:00:01",
                }
            ],
            get_or_create=lambda key: recent_session if key == "telegram:123" else None,
        ),
        channels=SimpleNamespace(
            enabled_channels=["telegram"],
            get_status=lambda: {"telegram": {"running": True, "connected": True}},
        ),
        cron=SimpleNamespace(
            status=lambda: {"enabled": True, "jobs": 0},
            list_jobs=lambda include_disabled=False: [],
            get_run_history=lambda job_id: [],
        ),
        config=cfg,
        agent=SimpleNamespace(subagents=SimpleNamespace(registry=SimpleNamespace(list_all=lambda: []))),
    )

    assert payload["recent_turn"]["session_key"] == "telegram:123"
    assert payload["recent_turn"]["continuity_source"] == "answer_reference"
    assert payload["recent_turn"]["turn_category"] == "chat"
    assert payload["recent_turn"]["required_tool"] == "weather"
    assert payload["recent_turn"]["required_tool_query"] == "cek suhu cilacap sekarang"
    assert payload["recent_turn"]["pending_interrupt_count"] == 2
    assert payload["recent_turn"]["completion_evidence"]["executed_tools"] == ["weather"]


def test_build_dashboard_status_payload_includes_command_surface(monkeypatch, tmp_path):
    from kabot.cli import commands
    from kabot.config.schema import Config
    from kabot.core.command_router import CommandRouter

    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path)

    router = CommandRouter()

    async def _status_handler(ctx):
        return "ok"

    router.register("/status", _status_handler, "Show status")
    router.register("/update", _status_handler, "Update bot", admin_only=True)

    class _Loader:
        def __init__(self, workspace, skills_config=None):
            pass

        def list_skills(self, filter_unavailable=False):
            return [
                {
                    "name": "meta-threads-official",
                    "skill_key": "meta-threads-official",
                    "eligible": True,
                    "disabled": False,
                    "description": "Connect to Meta Threads",
                    "primaryEnv": "",
                    "missing": {"env": [], "bins": [], "os": []},
                }
            ]

    monkeypatch.setattr("kabot.agent.skills.SkillsLoader", _Loader)
    monkeypatch.setattr("kabot.core.command_surfaces.SkillsLoader", _Loader)

    payload = commands._build_dashboard_status_payload(
        gateway_started_at=1709800000,
        runtime_model="gpt-4o-mini",
        runtime_fallbacks=[],
        runtime_host="127.0.0.1",
        runtime_port=18790,
        tailscale_mode="off",
        session_manager=SimpleNamespace(sessions_dir=tmp_path, list_sessions=lambda: []),
        channels=SimpleNamespace(enabled_channels=["telegram"], get_status=lambda: {}),
        cron=SimpleNamespace(
            status=lambda: {"enabled": True, "jobs": 0},
            list_jobs=lambda include_disabled=False: [],
            get_run_history=lambda job_id: [],
        ),
        config=cfg,
        agent=SimpleNamespace(
            workspace=tmp_path,
            command_router=router,
            subagents=SimpleNamespace(registry=SimpleNamespace(list_all=lambda: [])),
        ),
    )

    assert payload["command_surface"] == [
        {
            "name": "start",
            "description": "Start or resume the conversation",
            "source": "static",
            "skill_name": "",
            "admin_only": False,
        },
        {
            "name": "reset",
            "description": "Clear conversation context",
            "source": "static",
            "skill_name": "",
            "admin_only": False,
        },
        {
            "name": "help",
            "description": "Show available commands",
            "source": "static",
            "skill_name": "",
            "admin_only": False,
        },
        {
            "name": "status",
            "description": "Show status",
            "source": "router",
            "skill_name": "",
            "admin_only": False,
        },
        {
            "name": "update",
            "description": "Update bot",
            "source": "router",
            "skill_name": "",
            "admin_only": True,
        },
        {
            "name": "meta_threads_official",
            "description": "Connect to Meta Threads",
            "source": "skill",
            "skill_name": "meta-threads-official",
            "admin_only": False,
        },
    ]


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_cron_disable_updates_job_state():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    cron_job = SimpleNamespace(id="job-1", enabled=False, state=SimpleNamespace(next_run_at_ms=None))

    def _fake_enable_job(job_id: str, enabled: bool = True):
        if job_id == "job-1" and enabled is False:
            return cron_job
        return None

    result = await commands._gateway_dashboard_control_action(
        action="cron.disable",
        args={"job_id": "job-1"},
        config=cfg,
        save_config_fn=lambda _cfg: None,
        agent=SimpleNamespace(process_direct=None),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=SimpleNamespace(get_status=lambda: {}),
        cron=SimpleNamespace(enable_job=_fake_enable_job),
    )

    assert result["ok"] is True
    assert result["job_id"] == "job-1"
    assert result["enabled"] is False


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_cron_run_invokes_service():
    from kabot.cli import commands
    from kabot.config.schema import Config

    cfg = Config()
    state = {"job_id": None, "force": None}

    async def _fake_run_job(job_id: str, force: bool = False):
        state["job_id"] = job_id
        state["force"] = force
        return True

    result = await commands._gateway_dashboard_control_action(
        action="cron.run",
        args={"job_id": "job-1"},
        config=cfg,
        save_config_fn=lambda _cfg: None,
        agent=SimpleNamespace(process_direct=None),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=SimpleNamespace(get_status=lambda: {}),
        cron=SimpleNamespace(run_job=_fake_run_job),
    )

    assert result["ok"] is True
    assert result["job_id"] == "job-1"
    assert state == {"job_id": "job-1", "force": True}


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_skills_disable_persists_config():
    from kabot.cli import commands
    from kabot.config.schema import Config
    from kabot.config.skills_settings import get_skill_entry

    cfg = Config()
    saved = {"called": False}

    def _fake_save(updated_cfg):
        saved["called"] = True
        saved["cfg"] = updated_cfg

    result = await commands._gateway_dashboard_control_action(
        action="skills.disable",
        args={"skill_key": "demo-skill"},
        config=cfg,
        save_config_fn=_fake_save,
        agent=SimpleNamespace(process_direct=None),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=SimpleNamespace(get_status=lambda: {}),
    )

    entry = get_skill_entry(cfg.skills, "demo-skill")
    assert result["ok"] is True
    assert result["skill_key"] == "demo-skill"
    assert entry["enabled"] is False
    assert saved["called"] is True


@pytest.mark.asyncio
async def test_gateway_dashboard_control_action_skills_set_api_key_persists_config():
    from kabot.cli import commands
    from kabot.config.schema import Config
    from kabot.config.skills_settings import get_skill_entry

    cfg = Config()
    saved = {"called": False}

    def _fake_save(updated_cfg):
        saved["called"] = True
        saved["cfg"] = updated_cfg

    result = await commands._gateway_dashboard_control_action(
        action="skills.set_api_key",
        args={"skill_key": "demo-skill", "api_key": "secret-key"},
        config=cfg,
        save_config_fn=_fake_save,
        agent=SimpleNamespace(process_direct=None),
        session_manager=SimpleNamespace(list_sessions=lambda: []),
        channels=SimpleNamespace(get_status=lambda: {}),
    )

    entry = get_skill_entry(cfg.skills, "demo-skill")
    assert result["ok"] is True
    assert result["skill_key"] == "demo-skill"
    assert entry["api_key"] == "secret-key"
    assert saved["called"] is True
