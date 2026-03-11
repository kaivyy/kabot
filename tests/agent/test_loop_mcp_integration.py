from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop import AgentLoop
from kabot.bus.queue import MessageBus
from kabot.config.schema import Config
from kabot.cron.service import CronService
from kabot.providers.base import LLMResponse, ToolCallRequest


def _make_provider() -> MagicMock:
    provider = MagicMock()
    provider.get_default_model.return_value = "openai-codex/gpt-5.3-codex"
    provider.chat = AsyncMock(
        return_value=MagicMock(
            content="ok",
            has_tool_calls=False,
            tool_calls=[],
            reasoning_content=None,
        )
    )
    return provider


@pytest.mark.asyncio
async def test_agent_loop_leaves_mcp_disabled_when_feature_off(tmp_path):
    loop = AgentLoop(
        bus=MessageBus(),
        provider=_make_provider(),
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        config=Config(),
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )

    assert getattr(loop, "_mcp_enabled", False) is False
    assert await loop._ensure_mcp_session_runtime("cli:direct") is None


@pytest.mark.asyncio
async def test_agent_loop_registers_mcp_tool_for_active_session(monkeypatch, tmp_path):
    from kabot.mcp.session_state import activate_mcp_runtime

    config = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "fake_server"],
                    }
                },
            }
        }
    )
    loop = AgentLoop(
        bus=MessageBus(),
        provider=_make_provider(),
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        config=config,
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )

    class _FakeTransport:
        async def list_tools(self):
            return [
                SimpleNamespace(
                    name="echo",
                    description="Echo text",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                        },
                        "required": ["text"],
                    },
                )
            ]

        async def call_tool(self, tool_name, arguments=None):
            text = (arguments or {}).get("text", "")
            return {
                "is_error": False,
                "text": f"{tool_name}:{text}",
                "structured_content": {"echo": text},
            }

        async def close(self):
            return None

    monkeypatch.setattr("kabot.mcp.runtime.build_transport_for_server", lambda _definition: _FakeTransport())

    runtime = await loop._ensure_mcp_session_runtime("cli:direct")
    await loop._ensure_mcp_tools_loaded("cli:direct")

    assert runtime is not None
    assert loop.tools.has("mcp__local__echo") is True

    with activate_mcp_runtime(runtime):
        result = await loop.tools.execute("mcp__local__echo", {"text": "halo"})

    assert "halo" in result


@pytest.mark.asyncio
async def test_agent_loop_process_direct_exposes_mcp_tool_to_llm(monkeypatch, tmp_path):
    config = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "fake_server"],
                    }
                },
            }
        }
    )
    provider = _make_provider()
    observed_tool_names: list[str] = []

    async def _chat(**kwargs):
        tool_defs = kwargs.get("tools") or []
        observed_tool_names.extend(
            tool_def.get("function", {}).get("name", "")
            for tool_def in tool_defs
            if isinstance(tool_def, dict)
        )
        messages = kwargs["messages"]
        has_tool_result = any(
            isinstance(item, dict)
            and item.get("role") == "tool"
            and item.get("name") == "mcp__local__echo"
            for item in messages
        )
        if not has_tool_result:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="mcp__local__echo",
                        arguments={"text": "halo"},
                    )
                ],
            )
        return LLMResponse(content="Selesai: halo", tool_calls=[])

    provider.chat = AsyncMock(side_effect=_chat)
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        config=config,
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )

    class _FakeTransport:
        async def list_tools(self):
            return [
                SimpleNamespace(
                    name="echo",
                    description="Echo text",
                    inputSchema={
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                )
            ]

        async def call_tool(self, tool_name, arguments=None):
            return {
                "is_error": False,
                "text": f"{tool_name}:{(arguments or {}).get('text', '')}",
                "structured_content": {"echo": (arguments or {}).get("text", "")},
            }

        async def close(self):
            return None

    monkeypatch.setattr("kabot.mcp.runtime.build_transport_for_server", lambda _definition: _FakeTransport())

    result = await loop.process_direct("Gunakan tool MCP echo untuk menulis halo.", session_key="cli:direct")

    assert "mcp__local__echo" in observed_tool_names
    assert "halo" in result.lower()


@pytest.mark.asyncio
async def test_agent_loop_process_direct_recovers_missing_mcp_args_from_explicit_query(
    monkeypatch,
    tmp_path,
):
    config = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local_echo": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "fake_server"],
                    }
                },
            }
        }
    )
    provider = _make_provider()

    async def _chat(**kwargs):
        messages = kwargs["messages"]
        has_tool_result = any(
            isinstance(item, dict)
            and item.get("role") == "tool"
            and item.get("name") == "mcp__local_echo__echo"
            and "halo-mcp-local" in str(item.get("content", ""))
            for item in messages
        )
        if not has_tool_result:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="mcp__local_echo__echo",
                        arguments={},
                    )
                ],
            )
        return LLMResponse(content="Selesai: halo-mcp-local", tool_calls=[])

    provider.chat = AsyncMock(side_effect=_chat)
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        config=config,
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )

    class _FakeTransport:
        async def list_tools(self):
            return [
                SimpleNamespace(
                    name="echo",
                    description="Echo text",
                    inputSchema={
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                )
            ]

        async def call_tool(self, tool_name, arguments=None):
            return {
                "is_error": False,
                "text": f"{tool_name}:{(arguments or {}).get('text', '')}",
                "structured_content": {"echo": (arguments or {}).get("text", "")},
            }

        async def close(self):
            return None

    monkeypatch.setattr("kabot.mcp.runtime.build_transport_for_server", lambda _definition: _FakeTransport())

    result = await loop.process_direct(
        "Gunakan tool mcp.local_echo.echo dengan argumen text='halo-mcp-local' lalu tampilkan hasilnya saja.",
        session_key="cli:direct",
    )

    assert "halo-mcp-local" in result


@pytest.mark.asyncio
async def test_agent_loop_builds_explicit_mcp_context_note(monkeypatch, tmp_path):
    config = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "fake_server"],
                    }
                },
            }
        }
    )
    loop = AgentLoop(
        bus=MessageBus(),
        provider=_make_provider(),
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        config=config,
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )

    class _FakeTransport:
        async def list_tools(self):
            return []

        async def list_resources(self):
            return [
                SimpleNamespace(
                    name="Field Guide",
                    uri="memory://field-guide",
                    description="Local field notes",
                    mimeType="text/markdown",
                )
            ]

        async def read_resource(self, uri):
            return {"text": f"# Field Guide\n\nLoaded from {uri}"}

        async def list_prompts(self):
            return [
                SimpleNamespace(
                    name="briefing",
                    description="Mission briefing",
                    arguments=[],
                )
            ]

        async def get_prompt(self, prompt_name, arguments=None):
            return {"text": "Mission goal: evacuation"}

        async def call_tool(self, tool_name, arguments=None):
            return {"is_error": False, "text": "", "structured_content": None}

        async def close(self):
            return None

    monkeypatch.setattr("kabot.mcp.runtime.build_transport_for_server", lambda _definition: _FakeTransport())

    note = await loop._build_explicit_mcp_context_note(
        "cli:direct",
        prompt_ref=("local", "briefing"),
        resource_ref=("local", "memory://field-guide"),
    )

    assert "[MCP Prompt Context]" in note
    assert "Mission goal: evacuation" in note
    assert "[MCP Resource Context]" in note
    assert "Loaded from memory://field-guide" in note
