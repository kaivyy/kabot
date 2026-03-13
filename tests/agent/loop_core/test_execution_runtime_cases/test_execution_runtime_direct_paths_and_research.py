"""Split from tests/agent/loop_core/test_execution_runtime.py to keep test modules below 1000 lines.
Chunk 3: test_run_agent_loop_direct_read_file_analysis_returns_summary_via_provider_chat .. test_run_agent_loop_short_followup_skips_plan_and_critic_even_with_long_effective_context.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.execution_runtime import (
    call_llm_with_fallback,
    run_agent_loop,
)
from kabot.bus.events import InboundMessage
from kabot.providers.base import LLMResponse, ToolCallRequest


def _make_loop() -> SimpleNamespace:
    return SimpleNamespace(
        context_guard=SimpleNamespace(check_overflow=lambda _messages, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
        _resolve_models_for_message=lambda _msg: [
            "openai-codex/gpt-5.3-codex",
            "groq/llama3-70b-8192",
        ],
        _call_llm_with_fallback=AsyncMock(
            return_value=(LLMResponse(content="fallback-response"), None)
        ),
    )

@pytest.mark.asyncio
async def test_run_agent_loop_direct_read_file_analysis_returns_summary_via_provider_chat():
    direct_result = '<style>body{font-family:"Consolas","Courier New",monospace;}</style>'
    summarized = "Font yang dipakai adalah Consolas dengan fallback Courier New."
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "read_file",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=direct_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content=summarized))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="font di file ini",
        metadata={"file_analysis_mode": True},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == summarized
    loop._execute_required_tool_fallback.assert_awaited_once_with("read_file", msg)
    loop.provider.chat.assert_awaited_once()

@pytest.mark.asyncio
async def test_run_agent_loop_direct_list_dir_returns_raw_without_summary_chat():
    raw_result = "📁 bot\n📁 openclaw\n📄 README.md"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "list_dir",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="cek isi desktop")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("list_dir", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_direct_find_files_returns_raw_without_summary_chat():
    raw_result = "FILE report.pdf\nFILE reports/report-q1.pdf"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "find_files",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="cari file report.pdf")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("find_files", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_message_returns_raw_without_summary_chat():
    raw_result = "Message sent to telegram:8086"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "message",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content=r"kirim file C:\Users\Arvy Kairi\Desktop\report.pdf ke chat ini",
        metadata={"required_tool": "message"},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("message", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_message_resolves_bare_filename_from_last_folder_context(tmp_path):
    report_dir = tmp_path / "bot"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "TELEGRAM_DEMO.md"
    report_path.write_text("demo", encoding="utf-8")

    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "message",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value="Message sent to telegram:chat-1"),
        workspace=tmp_path,
        tools=SimpleNamespace(has=lambda name: name == "message"),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="kirim file TELEGRAM_DEMO.md kesini",
        metadata={
            "required_tool": "message",
            "requires_message_delivery": True,
            "last_tool_context": {"tool": "list_dir", "path": str(report_dir)},
        },
    )
    session = SimpleNamespace(metadata={"last_tool_context": {"tool": "list_dir", "path": str(report_dir)}})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Message sent to telegram:chat-1"
    loop._execute_required_tool_fallback.assert_awaited_once_with("message", msg)
    assert msg.metadata.get("message_delivery_verified") is True
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["artifact_verified"] is True
    assert str(report_path.resolve()) in evidence["artifact_paths"]


@pytest.mark.asyncio
async def test_run_agent_loop_direct_find_then_send_workflow_bypasses_llm(tmp_path):
    report_path = tmp_path / "report.pdf"
    report_path.write_text("report", encoding="utf-8")
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cari file report.pdf lalu kirim ke chat ini",
        metadata={
            "continuity_source": "action_request",
            "requires_message_delivery": True,
            "effective_content": "cari file report.pdf lalu kirim ke chat ini",
        },
    )
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(
            side_effect=[
                f"FILE {report_path}",
                "Message sent to telegram:chat-1",
            ]
        ),
        workspace=tmp_path,
        tools=SimpleNamespace(has=lambda name: name in {"find_files", "message"}),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("executed_tools") == ["find_files", "message"]
    assert msg.metadata.get("message_delivery_verified") is True
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["artifact_paths"] == [str(report_path)]
    assert evidence["artifact_verified"] is True
    assert evidence["delivery_verified"] is True
    assert loop._execute_required_tool_fallback.await_args_list[0].args == ("find_files", msg)
    assert loop._execute_required_tool_fallback.await_args_list[1].args == ("message", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_find_then_send_workflow_uses_primary_match_when_search_returns_multiple_paths(tmp_path):
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cari file CHANGELOG.md di folder kerja saat ini lalu kirim ke chat ini",
        metadata={
            "continuity_source": "action_request",
            "requires_message_delivery": True,
            "effective_content": "cari file CHANGELOG.md di folder kerja saat ini lalu kirim ke chat ini",
        },
    )
    primary_path = tmp_path / "CHANGELOG.md"
    primary_path.write_text("main changelog", encoding="utf-8")
    secondary_path = tmp_path / ".worktrees" / "feature-a" / "CHANGELOG.md"
    secondary_path.parent.mkdir(parents=True, exist_ok=True)
    secondary_path.write_text("feature changelog", encoding="utf-8")
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
            _execute_required_tool_fallback=AsyncMock(
                side_effect=[
                    f"FILE {primary_path}\nFILE {secondary_path}",
                    "Message sent to telegram:chat-1",
                ]
            ),
            workspace=tmp_path,
            tools=SimpleNamespace(has=lambda name: name in {"find_files", "message"}),
            provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
            bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        )

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("executed_tools") == ["find_files", "message"]
    assert msg.metadata.get("message_delivery_verified") is True
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["artifact_paths"] == [str(primary_path)]
    assert evidence["artifact_verified"] is True
    assert evidence["delivery_verified"] is True
    assert msg.metadata.get("last_tool_context", {}).get("path") == str(primary_path)
    assert loop._execute_required_tool_fallback.await_args_list[0].args == ("find_files", msg)
    assert loop._execute_required_tool_fallback.await_args_list[1].args == ("message", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_find_folder_then_send_workflow_archives_before_sending(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    archive_path = tmp_path / "reports.zip"
    archive_path.write_text("zip", encoding="utf-8")
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cari folder reports lalu kirim ke chat ini",
        metadata={
            "continuity_source": "action_request",
            "requires_message_delivery": True,
            "effective_content": "cari folder reports lalu kirim ke chat ini",
        },
    )
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(
            side_effect=[
                f"DIR {reports_dir}",
                f"Created archive {archive_path} from {reports_dir}",
                "Message sent to telegram:chat-1",
            ]
        ),
        workspace=tmp_path,
        tools=SimpleNamespace(has=lambda name: name in {"find_files", "archive_path", "message"}),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("executed_tools") == ["find_files", "archive_path", "message"]
    assert msg.metadata.get("message_delivery_verified") is True
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["artifact_paths"] == [str(archive_path)]
    assert evidence["artifact_verified"] is True
    assert evidence["delivery_verified"] is True
    assert msg.metadata.get("last_tool_context", {}).get("path") == str(archive_path)
    assert loop._execute_required_tool_fallback.await_args_list[0].args == ("find_files", msg)
    assert loop._execute_required_tool_fallback.await_args_list[1].args == ("archive_path", msg)
    assert loop._execute_required_tool_fallback.await_args_list[2].args == ("message", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_write_then_send_workflow_bypasses_llm(tmp_path):
    report_path = tmp_path / ".smoke_tmp" / "report.txt"
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="buat file .smoke_tmp/report.txt berisi HALO lalu kirim ke chat ini",
        metadata={
            "continuity_source": "action_request",
            "requires_message_delivery": True,
            "effective_content": "buat file .smoke_tmp/report.txt berisi HALO lalu kirim ke chat ini",
            "required_tool": "write_file",
        },
    )
    async def _direct_tool(tool_name, _msg):
        if tool_name == "write_file":
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("HALO", encoding="utf-8")
            return f"Successfully wrote 4 bytes to {report_path}"
        if tool_name == "message":
            return "Message sent to telegram:chat-1"
        raise AssertionError(tool_name)

    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "write_file",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(side_effect=_direct_tool),
        workspace=tmp_path,
        tools=SimpleNamespace(has=lambda name: name in {"write_file", "message"}),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("executed_tools") == ["write_file", "message"]
    assert msg.metadata.get("message_delivery_verified") is True
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["artifact_paths"] == [str(report_path)]
    assert evidence["artifact_verified"] is True
    assert evidence["delivery_verified"] is True
    assert loop._execute_required_tool_fallback.await_args_list[0].args == ("write_file", msg)
    assert loop._execute_required_tool_fallback.await_args_list[1].args == ("message", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_write_then_send_rejects_missing_artifact_without_completion_evidence(tmp_path):
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="buat file .smoke_tmp/report.txt berisi HALO lalu kirim ke chat ini",
        metadata={
            "continuity_source": "action_request",
            "requires_message_delivery": True,
            "effective_content": "buat file .smoke_tmp/report.txt berisi HALO lalu kirim ke chat ini",
            "required_tool": "write_file",
        },
    )
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "write_file",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(
            side_effect=[
                "Successfully wrote 4 bytes to .smoke_tmp/report.txt",
                "Message sent to telegram:chat-1",
            ]
        ),
        workspace=tmp_path,
        tools=SimpleNamespace(has=lambda name: name in {"write_file", "message"}),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert "couldn't verify the requested artifact" in result.lower()
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["artifact_paths"] == [str(tmp_path / ".smoke_tmp" / "report.txt")]
    assert evidence["artifact_verified"] is False
    assert evidence["delivery_verified"] is False
    loop._execute_required_tool_fallback.assert_awaited_once_with("write_file", msg)


@pytest.mark.asyncio
async def test_run_agent_loop_direct_image_then_send_workflow_bypasses_llm(tmp_path):
    image_path = tmp_path / "gen_abcd.png"
    session = SimpleNamespace(metadata={})
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="generate gambar poster kopi pakai imagen lalu kirim ke chat ini",
        metadata={
            "continuity_source": "action_request",
            "requires_message_delivery": True,
            "effective_content": "generate gambar poster kopi pakai imagen lalu kirim ke chat ini",
            "required_tool": "image_gen",
        },
    )
    async def _direct_tool(tool_name, _msg):
        if tool_name == "image_gen":
            image_path.write_text("png", encoding="utf-8")
            return f"Image generated via OpenAI: {image_path}"
        if tool_name == "message":
            return "Message sent to telegram:chat-1"
        raise AssertionError(tool_name)

    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "image_gen",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(side_effect=_direct_tool),
        workspace=tmp_path,
        tools=SimpleNamespace(has=lambda name: name in {"image_gen", "message"}),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("executed_tools") == ["image_gen", "message"]
    assert msg.metadata.get("message_delivery_verified") is True
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["artifact_paths"] == [str(image_path)]
    assert evidence["artifact_verified"] is True
    assert evidence["delivery_verified"] is True
    assert loop._execute_required_tool_fallback.await_args_list[0].args == ("image_gen", msg)
    assert loop._execute_required_tool_fallback.await_args_list[1].args == ("message", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_read_only_tool_returns_summary_via_provider_chat():
    direct_result = "cpu=17%, mem=42%, disk=61%"
    summarized = "System looks healthy: CPU 17%, memory 42%, disk 61%."
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "get_system_info",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=direct_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content=summarized))),
    )

    msg = InboundMessage(channel="cli", chat_id="direct", sender_id="user", content="cek system info")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == summarized
    loop._execute_required_tool_fallback.assert_awaited_once_with("get_system_info", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_awaited_once()

@pytest.mark.asyncio
async def test_run_agent_loop_direct_web_search_returns_raw_without_summary_chat():
    raw_result = "Results for: perang us israel iran\\n1. Reuters\\n2. AP"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "web_search",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="carikan berita perang us israel vs iran")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("web_search", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_direct_system_update_returns_raw_without_summary_chat():
    raw_result = "Berhasil update dari 0.5.8 ke 0.5.9. Restart diperlukan."
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "system_update",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="update kabot sekarang")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("system_update", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_direct_weather_returns_raw_without_summary_chat():
    raw_result = "Purwokerto: [Cloudy] +27C\nSaran: Bawa payung."
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "weather",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="cek suhu purwokerto sekarang")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("weather", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_direct_weather_updates_session_followup_context_from_resolved_query():
    raw_result = "Cilacap: [Cloudy] +24.7C | Wind: 3.5 km/h @ 336°"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "weather",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="ya",
        metadata={
            "required_tool": "weather",
            "required_tool_query": "cek suhu cilacap sekarang",
            "effective_content": "cek suhu cilacap sekarang",
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    followup = session.metadata.get("pending_followup_tool")
    assert isinstance(followup, dict)
    assert followup.get("tool") == "weather"
    assert "cilacap" in str(followup.get("source") or "").lower()
    last_ctx = session.metadata.get("last_tool_context")
    assert isinstance(last_ctx, dict)
    assert last_ctx.get("tool") == "weather"
    assert "cilacap" in str(last_ctx.get("source") or "").lower()

@pytest.mark.asyncio
async def test_run_agent_loop_uses_required_tool_from_message_metadata():
    raw_result = "Results for: berita terbaru 2026 sekarang\n1. Reuters"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="gas",
        metadata={
            "required_tool": "web_search",
            "required_tool_query": "berita terbaru 2026 sekarang",
            "route_profile": "RESEARCH",
            "effective_content": "berita terbaru 2026 sekarang",
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": "berita terbaru 2026 sekarang"}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("web_search", msg)
    loop._plan_task.assert_not_awaited()
    loop.provider.chat.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_heartbeat_skips_self_eval_and_critic():
    loop = SimpleNamespace(
        max_iterations=1,
        context_guard=SimpleNamespace(check_overflow=lambda _messages, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _is_weak_model=lambda _model: False,
        _required_tool_for_query=lambda _text: None,
        _plan_task=AsyncMock(return_value="1. check"),
        _apply_think_mode=lambda messages, _session: messages,
        _call_llm_with_fallback=AsyncMock(return_value=(LLMResponse(content="heartbeat-ok"), None)),
        _self_evaluate=MagicMock(return_value=(False, "nudge")),
        _critic_evaluate=AsyncMock(return_value=(1, "retry")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(),
        _execute_required_tool_fallback=AsyncMock(return_value="fallback"),
        _should_log_verbose=lambda _session: False,
        context=SimpleNamespace(
            add_assistant_message=lambda messages, content, reasoning_content=None: messages
            + [{"role": "assistant", "content": content}]
        ),
        provider=SimpleNamespace(),
    )

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="Heartbeat task: Autopilot patrol: review recent context and schedules",
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "heartbeat-ok"
    loop._plan_task.assert_awaited_once()
    loop._self_evaluate.assert_not_called()
    loop._critic_evaluate.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_uses_neutral_status_when_tool_calls_have_completion_text():
    bus = SimpleNamespace(publish_outbound=AsyncMock(return_value=None))
    first = LLMResponse(
        content="Cleanup selesai total",
        tool_calls=[ToolCallRequest(id="call_1", name="cleanup_system", arguments={"level": "standard"})],
    )
    second = LLMResponse(content="Tool finished", tool_calls=[])

    loop = SimpleNamespace(
        max_iterations=2,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(side_effect=[(first, None), (second, None)]),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        bus=bus,
        provider=SimpleNamespace(),
    )

    msg = InboundMessage(channel="cli", chat_id="direct", sender_id="user", content="tolong bersihkan cache")
    session = SimpleNamespace(metadata={})

    await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    outbound_texts = [call.args[0].content for call in bus.publish_outbound.await_args_list]
    assert "Cleanup selesai total" not in outbound_texts
    assert any(
        ("processing your request" in text.lower()) or ("sedang memproses permintaan" in text.lower())
        for text in outbound_texts
    )

@pytest.mark.asyncio
async def test_run_agent_loop_uses_neutral_status_when_tool_calls_have_empty_content():
    bus = SimpleNamespace(publish_outbound=AsyncMock(return_value=None))
    first = LLMResponse(
        content="",
        tool_calls=[ToolCallRequest(id="call_1", name="cleanup_system", arguments={"level": "standard"})],
    )
    second = LLMResponse(content="Tool finished", tool_calls=[])

    loop = SimpleNamespace(
        max_iterations=2,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(side_effect=[(first, None), (second, None)]),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        bus=bus,
        provider=SimpleNamespace(),
    )

    msg = InboundMessage(channel="cli", chat_id="direct", sender_id="user", content="tolong bersihkan cache")
    session = SimpleNamespace(metadata={})

    await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    outbound_texts = [call.args[0].content for call in bus.publish_outbound.await_args_list]
    assert any(
        ("processing your request" in text.lower()) or ("sedang memproses permintaan" in text.lower())
        for text in outbound_texts
    )

@pytest.mark.asyncio
async def test_run_agent_loop_skips_critic_for_short_fast_prompt():
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(LLMResponse(content="RAM total 16 GB"), None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(2, "retry")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        provider=SimpleNamespace(),
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="kapasitas ram berapa")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "RAM total 16 GB"
    loop._call_llm_with_fallback.assert_awaited_once()
    loop._critic_evaluate.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_skips_critic_for_research_route_even_when_prompt_is_long():
    long_query = (
        "carikan update paling terbaru dari sumber terpercaya tentang perkembangan konflik "
        "regional dan dampak ekonominya sampai saat ini"
    )
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(LLMResponse(content="Ringkasan awal"), None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(2, "retry")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        provider=SimpleNamespace(),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content=long_query,
        metadata={"route_profile": "RESEARCH"},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Ringkasan awal"
    loop._call_llm_with_fallback.assert_awaited_once()
    loop._critic_evaluate.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_publishes_draft_update_before_critic_retry():
    bus = SimpleNamespace(publish_outbound=AsyncMock(return_value=None))
    first = LLMResponse(content="Jawaban awal ini masih terlalu umum dan perlu diperbaiki.", tool_calls=[])
    second = LLMResponse(content="Jawaban final ini lebih lengkap dan presisi.", tool_calls=[])

    loop = SimpleNamespace(
        max_iterations=2,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(side_effect=[(first, None), (second, None)]),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(side_effect=[(2, "perbaiki"), (9, "ok")]),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        bus=bus,
        provider=SimpleNamespace(),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086618307",
        sender_id="user",
        content="Tolong jelaskan kondisi penggunaan memori sistem saya saat ini dengan ringkas dan jelas.",
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == second.content
    outbound = [call.args[0] for call in bus.publish_outbound.await_args_list]
    draft_updates = [
        item
        for item in outbound
        if isinstance(item.metadata, dict) and item.metadata.get("type") == "draft_update"
    ]
    assert draft_updates
    assert any("Jawaban awal" in str(item.content) for item in draft_updates)

@pytest.mark.asyncio
async def test_run_agent_loop_publishes_reasoning_lane_update_when_available():
    bus = SimpleNamespace(publish_outbound=AsyncMock(return_value=None))
    response = LLMResponse(
        content="Berikut ringkasan terbaru.",
        tool_calls=[],
        reasoning_content="Checking trusted sources and validating timestamps before final answer.",
    )

    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(response, None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs
            + [{"role": "assistant", "content": content, "reasoning_content": reasoning_content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        bus=bus,
        provider=SimpleNamespace(),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086618307",
        sender_id="user",
        content="carikan update terbaru global",
        metadata={"skip_critic_for_speed": True},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == response.content
    outbound = [call.args[0] for call in bus.publish_outbound.await_args_list]
    reasoning_updates = [
        item
        for item in outbound
        if isinstance(item.metadata, dict)
        and item.metadata.get("type") == "reasoning_update"
        and item.metadata.get("lane") == "reasoning"
    ]
    assert reasoning_updates

@pytest.mark.asyncio
async def test_call_llm_with_fallback_blocks_when_quota_hard_limit_exceeded():
    provider = SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="ok")))
    loop = SimpleNamespace(
        provider=provider,
        tools=SimpleNamespace(get_definitions=lambda: []),
        auth_rotation=None,
        resilience=SimpleNamespace(handle_error=AsyncMock(), on_success=lambda: None),
        runtime_resilience=SimpleNamespace(max_model_attempts_per_turn=4, strict_error_classification=True),
        runtime_quotas=SimpleNamespace(
            enabled=True,
            max_cost_per_day_usd=0.0,
            max_tokens_per_hour=1,
            enforcement_mode="hard",
        ),
        last_model_used=None,
        last_fallback_used=False,
        last_model_chain=[],
        _active_turn_id="turn-hard-quota",
    )

    response, error = await call_llm_with_fallback(
        loop,
        [{"role": "user", "content": "this message should exceed tiny quota"}],
        ["openai/gpt-4o"],
    )

    assert response is None
    assert error is not None
    assert "quota" in str(error).lower()
    provider.chat.assert_not_awaited()

@pytest.mark.asyncio
async def test_call_llm_with_fallback_warns_when_quota_warn_limit_exceeded(monkeypatch):
    warnings: list[str] = []
    monkeypatch.setattr(
        "kabot.agent.loop_core.execution_runtime.logger.warning",
        lambda message: warnings.append(str(message)),
    )

    provider = SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="ok")))
    loop = SimpleNamespace(
        provider=provider,
        tools=SimpleNamespace(get_definitions=lambda: []),
        auth_rotation=None,
        resilience=SimpleNamespace(handle_error=AsyncMock(), on_success=lambda: None),
        runtime_resilience=SimpleNamespace(max_model_attempts_per_turn=4, strict_error_classification=True),
        runtime_quotas=SimpleNamespace(
            enabled=True,
            max_cost_per_day_usd=0.0,
            max_tokens_per_hour=1,
            enforcement_mode="warn",
        ),
        last_model_used=None,
        last_fallback_used=False,
        last_model_chain=[],
        _active_turn_id="turn-warn-quota",
    )

    response, error = await call_llm_with_fallback(
        loop,
        [{"role": "user", "content": "this message should exceed tiny quota"}],
        ["openai/gpt-4o"],
    )

    assert error is None
    assert response is not None
    assert response.content == "ok"
    provider.chat.assert_awaited_once()
    assert any("quota" in item.lower() and "warn" in item.lower() for item in warnings)

@pytest.mark.asyncio
async def test_run_agent_loop_forces_web_search_for_live_query_even_without_research_route():
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _execute_required_tool_fallback=AsyncMock(return_value="live-result"),
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(LLMResponse(content="should-not-run"), None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(9, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        tools=SimpleNamespace(has=lambda name: name == "web_search"),
        provider=SimpleNamespace(),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="berita terbaru 2026 sekarang",
        metadata={"route_profile": "GENERAL"},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "live-result"
    loop._execute_required_tool_fallback.assert_awaited_once_with("web_search", msg)
    loop._call_llm_with_fallback.assert_not_awaited()

@pytest.mark.asyncio
async def test_run_agent_loop_research_route_does_not_force_web_search_for_general_advice_query():
    response = LLMResponse(content="Kalau cuaca panas, cari sunscreen SPF 30-50 yang nyaman dipakai harian.")
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _execute_required_tool_fallback=AsyncMock(return_value="search-result"),
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(response, None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(9, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        tools=SimpleNamespace(has=lambda name: name == "web_search"),
        provider=SimpleNamespace(),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="sunscreen nya apa yang bagus",
        metadata={"route_profile": "RESEARCH"},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert "sunscreen" in result.lower()
    loop._execute_required_tool_fallback.assert_not_awaited()
    loop._call_llm_with_fallback.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_agent_loop_does_not_force_web_search_for_personal_hr_zone_calculation():
    response = LLMResponse(content="HR max estimasi kamu 195 bpm.")
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _execute_required_tool_fallback=AsyncMock(return_value="search-result"),
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(response, None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(9, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        tools=SimpleNamespace(has=lambda name: name == "web_search"),
        provider=SimpleNamespace(),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="umurku sekarang 25 tahun tolong hitung zona hr personal",
        metadata={"route_profile": "GENERAL"},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert "195" in result
    loop._execute_required_tool_fallback.assert_not_awaited()
    loop._call_llm_with_fallback.assert_awaited_once()

@pytest.mark.asyncio
async def test_run_agent_loop_short_followup_skips_plan_and_critic_even_with_long_effective_context():
    response = LLMResponse(content="Siap, lanjut sekarang.")
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _execute_required_tool_fallback=AsyncMock(return_value=None),
        _plan_task=AsyncMock(return_value="1. Dummy plan"),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(response, None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(1, "retry")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(side_effect=lambda _msg, msgs, _resp, _sess: msgs),
        context=SimpleNamespace(
            add_assistant_message=lambda msgs, content, reasoning_content=None: msgs
            + [{"role": "assistant", "content": content}]
        ),
        context_guard=SimpleNamespace(check_overflow=lambda _m, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _is_weak_model=lambda _model: False,
        tools=SimpleNamespace(has=lambda _name: False),
        provider=SimpleNamespace(),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    long_followup_context = (
        "ya\n\n[Follow-up Context]\nPlease continue the previous execution details, "
        "validate latest sources, and summarize all findings in one final answer."
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="ya",
        metadata={
            "route_profile": "GENERAL",
            "effective_content": long_followup_context,
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "Siap, lanjut sekarang."
    loop._plan_task.assert_not_awaited()
    loop._critic_evaluate.assert_not_awaited()
