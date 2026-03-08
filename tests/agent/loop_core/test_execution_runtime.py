import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import kabot.agent.loop_core.execution_runtime as execution_runtime_module
from kabot.agent.context import ContextBuilder
from kabot.agent.loop_core.execution_runtime import (
    _sanitize_error,
    call_llm_with_fallback,
    process_tool_calls,
    run_agent_loop,
    run_simple_response,
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
async def test_run_simple_response_uses_model_chain_fallback():
    loop = _make_loop()
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="halo",
    )
    messages = [{"role": "user", "content": "halo"}]

    result = await run_simple_response(loop, msg, messages)

    assert result == "fallback-response"
    loop._call_llm_with_fallback.assert_awaited_once_with(
        messages,
        ["openai-codex/gpt-5.3-codex", "groq/llama3-70b-8192"],
    )
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_simple_response_error_message_is_utf8_safe():
    loop = _make_loop()
    loop._call_llm_with_fallback = AsyncMock(
        return_value=(None, Exception("Authentication failed: 401"))
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="halo",
    )
    messages = [{"role": "user", "content": "halo"}]

    result = await run_simple_response(loop, msg, messages)

    assert "Authentication failed: 401" in result
    # Reproduces Telegram transport encoding path: must never raise UnicodeEncodeError.
    result.encode("utf-8")


def test_sanitize_error_replaces_invalid_surrogates():
    raw_error = "Authentication failed: token \ud83d expired"

    sanitized = _sanitize_error(raw_error)

    sanitized.encode("utf-8")
    assert "\ud83d" not in sanitized


@pytest.mark.asyncio
async def test_run_agent_loop_respects_suppressed_required_tool_inference():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: "weather"
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="weather-result")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(True, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 1
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="sunscreen yang bagus buat cuaca panas apa ya?",
        metadata={
            "effective_content": "sunscreen yang bagus buat cuaca panas apa ya?",
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "suppress_required_tool_inference": True,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert result == "fallback-response"
    loop._execute_required_tool_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_tool_calls_preserves_assistant_tool_calls_with_content(tmp_path):
    tool_executor = AsyncMock(return_value="scheduled")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(
            get=lambda _name: None,
            execute=tool_executor,
        ),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086618307",
        sender_id="user",
        content="ingatkan 2 menit lagi",
    )
    response = LLMResponse(
        content="Scheduling task",
        tool_calls=[ToolCallRequest(id="call_abc", name="cron", arguments={"action": "add"})],
    )
    messages = [
        {"role": "user", "content": "ingatkan 2 menit lagi"},
        {"role": "assistant", "content": "Scheduling task"},
    ]

    updated = await process_tool_calls(loop, msg, messages, response, session=SimpleNamespace(metadata={}))

    assistant_entries = [m for m in updated if m.get("role") == "assistant"]
    assert len(assistant_entries) == 1
    assert assistant_entries[0].get("tool_calls")
    assert assistant_entries[0]["tool_calls"][0]["id"] == "call_abc"
    assert any(m.get("role") == "tool" and m.get("tool_call_id") == "call_abc" for m in updated)


@pytest.mark.asyncio
async def test_process_tool_calls_emits_tool_phase_status_metadata(tmp_path):
    bus = SimpleNamespace(publish_outbound=AsyncMock(return_value=None))
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=AsyncMock(return_value="done")),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: "Checking weather now...",
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=bus,
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="cek cuaca")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_weather", name="weather", arguments={"location": "Jakarta"})],
    )

    await process_tool_calls(loop, msg, [{"role": "user", "content": msg.content}], response, session=SimpleNamespace(metadata={}))

    outbound = [call.args[0] for call in bus.publish_outbound.await_args_list]
    tool_status = next(item for item in outbound if (item.metadata or {}).get("type") == "status_update")
    assert tool_status.metadata.get("phase") == "tool"
    assert tool_status.metadata.get("lane") == "status"


@pytest.mark.asyncio
async def test_process_tool_calls_applies_channel_hard_cap_to_tool_result(tmp_path):
    very_large_output = "X" * 25000
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=AsyncMock(return_value=very_large_output)),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="cek cuaca")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_weather", name="weather", arguments={"location": "Jakarta"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_messages = [m for m in updated if m.get("role") == "tool"]
    assert tool_messages
    # Telegram lane should be capped much lower than raw 25k chars for token safety.
    assert len(str(tool_messages[-1].get("content") or "")) < 10000


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_stock_for_non_stock_file_query(tmp_path):
    tool_executor = AsyncMock(return_value="[STOCK] CONFIG.JSON ...")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="baca file config.json")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_stock", name="stock", arguments={"symbol": "CONFIG.JSON"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_stock"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_write_file_before_skill_plan_approval(tmp_path):
    tool_executor = AsyncMock(return_value="written")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="oke bikin skill threads sekarang",
        metadata={
            "skill_creation_guard": {
                "active": True,
                "stage": "planning",
                "approved": False,
                "request_text": "buat skill baru untuk Threads API",
            }
        },
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_write_skill", name="write_file", arguments={"path": "skills/meta-threads/SKILL.md", "content": "# Threads"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_write_skill"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_SKILL_CREATION_APPROVAL" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_allows_write_file_after_skill_plan_approval(tmp_path):
    tool_executor = AsyncMock(return_value="written")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="oke, implementasikan sekarang",
        metadata={
            "skill_creation_guard": {
                "active": True,
                "stage": "approved",
                "approved": True,
                "request_text": "buat skill baru untuk Threads API",
            }
        },
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_write_skill", name="write_file", arguments={"path": "skills/meta-threads/SKILL.md", "content": "# Threads"})],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_stock_for_non_action_stock_feedback(tmp_path):
    tool_executor = AsyncMock(return_value="[STOCK] BBRI.JK ...")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="stop bahas saham")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_stock", name="stock", arguments={"symbol": "BBRI.JK"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_stock"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_stock_for_geopolitical_news_query(tmp_path):
    tool_executor = AsyncMock(return_value="[STOCK] BBRI.JK ...")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="adakah gejolak politik sekarang? saya dengar perang iran vs us israel ya",
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_stock", name="stock", arguments={"symbol": "BBRI.JK"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_stock"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_stock_for_geopolitical_query_even_without_web_search_tool(tmp_path):
    tool_executor = AsyncMock(return_value="[STOCK] BBRI.JK ...")

    def _has_tool(name: str) -> bool:
        # Simulate deployments where web_search is disabled/misconfigured.
        return name != "web_search"

    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=_has_tool),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="adakah gejolak politik sekarang? saya dengar perang iran vs us israel ya",
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_stock", name="stock", arguments={"symbol": "BBRI.JK"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_stock"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_web_search_for_general_advice_query(tmp_path):
    tool_executor = AsyncMock(return_value="No results for: sunscreen")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="sunscreen nya apa yang bagus",
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_search", name="web_search", arguments={"query": msg.content})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_search"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_keeps_valid_web_search_execution(tmp_path):
    tool_executor = AsyncMock(return_value="Results for: perang iran terbaru 2026")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="carikan berita perang iran terbaru 2026 sekarang",
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_search", name="web_search", arguments={"query": msg.content})],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once_with("web_search", {"query": msg.content})


@pytest.mark.asyncio
async def test_process_tool_calls_keeps_required_web_search_for_multilingual_query(tmp_path):
    tool_executor = AsyncMock(return_value="Results for: ข่าวล่าสุดอิหร่าน")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="ข่าวล่าสุดอิหร่าน",
        metadata={"required_tool": "web_search"},
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_search", name="web_search", arguments={"query": msg.content})],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once_with("web_search", {"query": msg.content})


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_cron_for_low_information_greeting(tmp_path):
    tool_executor = AsyncMock(return_value="reminder-set")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="halo")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_cron", name="cron", arguments={"action": "add", "message": "x"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_cron"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_keeps_valid_stock_execution(tmp_path):
    tool_executor = AsyncMock(return_value="[STOCK] BBRI.JK ...")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="cek harga bbri sekarang")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_stock", name="stock", arguments={"symbol": "BBRI.JK"})],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once_with("stock", {"symbol": "BBRI.JK"})


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_weather_for_non_weather_greeting(tmp_path):
    tool_executor = AsyncMock(return_value="Jakarta: 30C")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="halo")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_weather", name="weather", arguments={"location": "Jakarta"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_weather"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_image_tool_for_non_image_intent(tmp_path):
    tool_executor = AsyncMock(return_value="Image generated via provider")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="cek harga bbri sekarang")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_img", name="image_gen", arguments={"prompt": "car in forest"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_img"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_allows_image_tool_for_image_intent(tmp_path):
    tool_executor = AsyncMock(return_value="Image generated via provider")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="buatkan gambar mobil di hutan",
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_img", name="image_gen", arguments={"prompt": "mobil di hutan"})],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once_with("image_gen", {"prompt": "mobil di hutan"})


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_tts_tool_for_non_tts_intent(tmp_path):
    tool_executor = AsyncMock(return_value="Audio generated")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="halo")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_tts", name="tts", arguments={"text": "hello"})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_tts"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_update_tool_when_intent_is_not_update(tmp_path):
    tool_executor = AsyncMock(return_value='{"update_available": false}')
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor, has=lambda _name: True),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="apa kabar")
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_update", name="check_update", arguments={})],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert tool_executor.await_count == 0
    tool_messages = [m for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_update"]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


def test_tool_result_hard_cap_is_stricter_in_hemat_mode():
    raw = "X" * 12000
    boros = execution_runtime_module._apply_channel_tool_result_hard_cap(
        raw,
        channel="telegram",
        tool_name="weather",
        token_mode="boros",
    )
    hemat = execution_runtime_module._apply_channel_tool_result_hard_cap(
        raw,
        channel="telegram",
        tool_name="weather",
        token_mode="hemat",
    )

    assert len(hemat) < len(boros)


@pytest.mark.asyncio
async def test_call_llm_with_fallback_uses_immutable_chain_snapshot():
    provider = SimpleNamespace(chat=AsyncMock(side_effect=[Exception("401 unauthorized"), Exception("429 rate limit")]))
    loop = SimpleNamespace(
        provider=provider,
        tools=SimpleNamespace(get_definitions=lambda: []),
        auth_rotation=None,
        resilience=SimpleNamespace(
            handle_error=AsyncMock(return_value={"action": "model_fallback", "new_model": "provider/model-c"}),
            on_success=lambda: None,
        ),
        runtime_resilience=SimpleNamespace(
            max_model_attempts_per_turn=8,
            strict_error_classification=True,
        ),
        last_model_used=None,
        last_fallback_used=False,
        last_model_chain=[],
    )

    models = ["provider/model-a", "provider/model-b"]
    response, error = await call_llm_with_fallback(loop, [{"role": "user", "content": "halo"}], models)

    assert response is None
    assert error is not None
    assert provider.chat.await_count == 2
    assert loop.last_model_chain == ["provider/model-a", "provider/model-b"]
    assert models == ["provider/model-a", "provider/model-b"]


@pytest.mark.asyncio
async def test_call_llm_with_fallback_text_only_retry_for_tool_protocol():
    async def _chat(**kwargs):
        if "tools" in kwargs:
            raise Exception("400 No tool call found for function call output")
        return LLMResponse(content="text-only-ok")

    provider = SimpleNamespace(chat=AsyncMock(side_effect=_chat))
    loop = SimpleNamespace(
        provider=provider,
        tools=SimpleNamespace(get_definitions=lambda: [{"name": "cron"}]),
        auth_rotation=None,
        resilience=SimpleNamespace(handle_error=AsyncMock(), on_success=lambda: None),
        runtime_resilience=SimpleNamespace(max_model_attempts_per_turn=4, strict_error_classification=True),
        last_model_used=None,
        last_fallback_used=False,
        last_model_chain=[],
    )

    response, error = await call_llm_with_fallback(
        loop,
        [{"role": "user", "content": "ingatkan"}],
        ["openai-codex/gpt-5.3-codex"],
    )

    assert error is None
    assert response is not None
    assert response.content == "text-only-ok"
    assert provider.chat.await_count == 2


@pytest.mark.asyncio
async def test_process_tool_calls_dedupes_duplicate_payload_within_turn(tmp_path):
    tool_executor = AsyncMock(return_value="scheduled")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(truncate=lambda value, _tool_name: value, _count_tokens=lambda _value: 0),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
        runtime_resilience=SimpleNamespace(dedupe_tool_calls=True, idempotency_ttl_seconds=600),
        runtime_performance=SimpleNamespace(fast_first_response=False),
        _active_turn_id="turn-1",
        _pending_memory_tasks=set(),
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="ingatkan")
    response = LLMResponse(
        content="Scheduling task",
        tool_calls=[
            ToolCallRequest(id="call_1", name="cron", arguments={"action": "add", "title": "A"}),
            ToolCallRequest(id="call_2", name="cron", arguments={"action": "add", "title": "A"}),
        ],
    )

    updated = await process_tool_calls(loop, msg, [{"role": "user", "content": "ingatkan"}], response, session=SimpleNamespace(metadata={}))

    assert tool_executor.await_count == 1
    assert sum(1 for m in updated if m.get("role") == "tool") == 2


@pytest.mark.asyncio
async def test_process_tool_calls_replayed_call_id_does_not_append_duplicate_tool_result(tmp_path):
    tool_executor = AsyncMock(return_value="scheduled")
    loop = SimpleNamespace(
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(get=lambda _name: None, execute=tool_executor),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(truncate=lambda value, _tool_name: value, _count_tokens=lambda _value: 0),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
        exec_auto_approve=False,
        runtime_resilience=SimpleNamespace(dedupe_tool_calls=True, idempotency_ttl_seconds=600),
        runtime_performance=SimpleNamespace(fast_first_response=False),
        _active_turn_id="turn-1",
        _pending_memory_tasks=set(),
        _tool_payload_cache={},
        _tool_call_id_cache={"call_same": (time.time() + 600, "cached-result")},
    )

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="ingatkan")
    response = LLMResponse(
        content="Scheduling task",
        tool_calls=[ToolCallRequest(id="call_same", name="cron", arguments={"action": "add", "title": "A"})],
    )

    prior_messages = [
        {"role": "user", "content": "ingatkan"},
        {
            "role": "assistant",
            "content": "Scheduling task",
            "tool_calls": [
                {"id": "call_same", "type": "function", "function": {"name": "cron", "arguments": "{\"action\":\"add\",\"title\":\"A\"}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "call_same", "name": "cron", "content": "cached-result"},
    ]

    updated = await process_tool_calls(loop, msg, prior_messages, response, session=SimpleNamespace(metadata={}))

    # Replay must not execute tool again.
    assert tool_executor.await_count == 0
    # Ensure no duplicate tool output is appended for the same replayed call id.
    assert sum(1 for m in updated if m.get("role") == "tool" and m.get("tool_call_id") == "call_same") == 1


@pytest.mark.asyncio
async def test_call_llm_with_fallback_disables_provider_internal_fallbacks():
    class _Provider:
        def __init__(self):
            self.fallbacks = ["provider/model-c"]
            self.calls = []

        async def chat(self, **kwargs):
            model = kwargs["model"]
            self.calls.append((model, list(self.fallbacks)))
            if model == "provider/model-a":
                # If provider-level fallback is still enabled, this would
                # incorrectly look like success on the primary attempt.
                if self.fallbacks:
                    return LLMResponse(content="provider-internal-fallback-success")
                raise Exception("429 rate limit")
            return LLMResponse(content="provider/model-b-success")

    provider = _Provider()
    loop = SimpleNamespace(
        provider=provider,
        tools=SimpleNamespace(get_definitions=lambda: []),
        auth_rotation=None,
        resilience=SimpleNamespace(
            handle_error=AsyncMock(return_value={"action": "model_fallback"}),
            on_success=lambda: None,
        ),
        runtime_resilience=SimpleNamespace(
            max_model_attempts_per_turn=4,
            strict_error_classification=True,
        ),
        last_model_used=None,
        last_fallback_used=False,
        last_model_chain=[],
    )

    response, error = await call_llm_with_fallback(
        loop,
        [{"role": "user", "content": "halo"}],
        ["provider/model-a", "provider/model-b"],
    )

    assert error is None
    assert response is not None
    assert response.content == "provider/model-b-success"
    assert provider.fallbacks == ["provider/model-c"]
    assert provider.calls[0][0] == "provider/model-a"
    assert provider.calls[0][1] == []
    assert provider.calls[1][0] == "provider/model-b"


@pytest.mark.asyncio
async def test_call_llm_with_fallback_treats_provider_error_payload_as_failure():
    provider = SimpleNamespace(
        fallbacks=[],
        chat=AsyncMock(
            side_effect=[
                LLMResponse(content="All models failed. Last error: 429", finish_reason="error"),
                LLMResponse(content="fallback-ok"),
            ]
        ),
    )
    loop = SimpleNamespace(
        provider=provider,
        tools=SimpleNamespace(get_definitions=lambda: []),
        auth_rotation=None,
        resilience=SimpleNamespace(handle_error=AsyncMock(), on_success=lambda: None),
        runtime_resilience=SimpleNamespace(max_model_attempts_per_turn=4, strict_error_classification=True),
        last_model_used=None,
        last_fallback_used=False,
        last_model_chain=[],
    )

    response, error = await call_llm_with_fallback(
        loop,
        [{"role": "user", "content": "halo"}],
        ["openai-codex/gpt-5.3-codex", "groq/meta-llama/llama-4-scout-17b-16e-instruct"],
    )

    assert error is None
    assert response is not None
    assert response.content == "fallback-ok"
    assert provider.chat.await_count == 2
    assert loop.last_model_used == "groq/meta-llama/llama-4-scout-17b-16e-instruct"
    assert loop.last_fallback_used is True


@pytest.mark.asyncio
async def test_run_agent_loop_heartbeat_does_not_force_cron_tool():
    loop = SimpleNamespace(
        max_iterations=1,
        context_guard=SimpleNamespace(check_overflow=lambda _messages, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _is_weak_model=lambda _model: True,
        _required_tool_for_query=lambda _text: "cron",
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda messages, _session: messages,
        _call_llm_with_fallback=AsyncMock(return_value=(LLMResponse(content="heartbeat-ok"), None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _process_tool_calls=AsyncMock(),
        _execute_required_tool_fallback=AsyncMock(return_value="fallback-cron"),
        _should_log_verbose=lambda _session: False,
        context=SimpleNamespace(
            add_assistant_message=lambda messages, content, reasoning_content=None: messages + [{"role": "assistant", "content": content}]
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
    loop._call_llm_with_fallback.assert_awaited_once()
    loop._execute_required_tool_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_run_agent_loop_direct_cleanup_returns_raw_result_without_summary_chat():
    raw_result = "cleanup: removed temp files"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "cleanup_system",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
    )

    msg = InboundMessage(channel="cli", chat_id="direct", sender_id="user", content="bersihkan sistem")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("cleanup_system", msg)
    loop._plan_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_status_text_comes_from_i18n_translator(monkeypatch):
    published = []

    async def _publish(msg):
        published.append(msg)

    def _fake_t(key: str, text: str | None = None, **kwargs) -> str:
        return f"<{key}>"

    monkeypatch.setattr(execution_runtime_module, "t", _fake_t)

    raw_result = "cleanup: removed temp files"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "cleanup_system",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(channel="telegram", chat_id="chat-1", sender_id="user", content="clean up")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    statuses = [m for m in published if (m.metadata or {}).get("type") == "status_update"]
    phases = [m.metadata.get("phase") for m in statuses]
    contents = [m.content for m in statuses]

    assert result == raw_result
    assert "thinking" in phases
    assert "tool" in phases
    assert "done" in phases
    assert "<runtime.status.thinking>" in contents
    assert "<runtime.status.tool>" in contents
    assert "<runtime.status.done>" in contents
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_status_text_uses_runtime_locale_from_message_metadata(monkeypatch):
    published = []
    seen_locales = []

    async def _publish(msg):
        published.append(msg)

    def _fake_t(key: str, text: str | None = None, **kwargs) -> str:
        seen_locales.append(kwargs.get("locale"))
        return f"<{kwargs.get('locale')}:{key}>"

    monkeypatch.setattr(execution_runtime_module, "t", _fake_t)

    raw_result = "weather: 28C"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "weather",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user",
        content="cek cuaca",
        metadata={"runtime_locale": "id"},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    statuses = [m for m in published if (m.metadata or {}).get("type") == "status_update"]
    contents = [m.content for m in statuses]
    assert result == raw_result
    assert any(text.startswith("<id:runtime.status.") for text in contents)
    assert "id" in seen_locales


@pytest.mark.asyncio
async def test_run_agent_loop_skips_thinking_and_done_phases_when_status_lane_not_mutable(monkeypatch):
    published = []

    async def _publish(msg):
        published.append(msg)

    def _fake_t(key: str, text: str | None = None, **kwargs) -> str:
        return f"<{key}>"

    monkeypatch.setattr(execution_runtime_module, "t", _fake_t)

    raw_result = "weather: 28C"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "weather",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(
        channel="whatsapp",
        chat_id="chat-1",
        sender_id="user",
        content="cek cuaca",
        metadata={"status_mutable_lane": False},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    statuses = [m for m in published if (m.metadata or {}).get("type") == "status_update"]
    phases = [m.metadata.get("phase") for m in statuses]
    assert result == raw_result
    assert "tool" in phases
    assert "thinking" not in phases
    assert "done" not in phases


@pytest.mark.asyncio
async def test_run_agent_loop_skips_initial_thinking_phase_when_already_bootstrapped_by_message_runtime(monkeypatch):
    published = []

    async def _publish(msg):
        published.append(msg)

    def _fake_t(key: str, text: str | None = None, **kwargs) -> str:
        return f"<{key}>"

    monkeypatch.setattr(execution_runtime_module, "t", _fake_t)

    raw_result = "weather: 28C"
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "weather",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user",
        content="cek cuaca",
        metadata={"suppress_initial_thinking_status": True},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    statuses = [m for m in published if (m.metadata or {}).get("type") == "status_update"]
    phases = [m.metadata.get("phase") for m in statuses]
    assert result == raw_result
    assert "thinking" not in phases


@pytest.mark.asyncio
async def test_run_agent_loop_uses_planning_phase_for_unapproved_skill_workflow(monkeypatch):
    published = []

    async def _publish(msg):
        published.append(msg)

    def _fake_t(key: str, text: str | None = None, **kwargs) -> str:
        return f"<{key}>"

    monkeypatch.setattr(execution_runtime_module, "t", _fake_t)

    loop = SimpleNamespace(
        max_iterations=1,
        context_guard=SimpleNamespace(check_overflow=lambda _messages, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(LLMResponse(content="Plan dulu ya"), None)),
        _execute_required_tool_fallback=AsyncMock(return_value=None),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="Plan dulu ya"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
        _should_log_verbose=lambda _session: False,
        _self_evaluate=lambda _question, _response: (True, None),
        _critic_evaluate=AsyncMock(return_value=(True, "")),
        _review_tool_output=AsyncMock(return_value=None),
        _get_last_tool_context=lambda _session: None,
        tools=SimpleNamespace(has=lambda _name: False),
        context=SimpleNamespace(
            add_assistant_message=lambda messages, content, tool_calls=None, reasoning_content=None: [
                *messages,
                {"role": "assistant", "content": content},
            ],
            add_tool_result=lambda messages, _id, _name, result: [*messages, {"role": "tool", "content": result}],
        ),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user",
        content="buat skill baru untuk Threads API",
        metadata={
            "runtime_locale": "en",
            "route_profile": "GENERAL",
            "skill_creation_guard": {
                "active": True,
                "stage": "planning",
                "approved": False,
                "request_text": "buat skill baru untuk Threads API",
            },
        },
    )

    session = SimpleNamespace(metadata={})

    await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    statuses = [m for m in published if (m.metadata or {}).get("type") == "status_update"]
    phases = [m.metadata.get("phase") for m in statuses]
    assert "planning" in phases


@pytest.mark.asyncio
async def test_run_agent_loop_uses_executing_and_verified_phases_for_approved_skill_workflow(monkeypatch):
    published = []

    async def _publish(msg):
        published.append(msg)

    def _fake_t(key: str, text: str | None = None, **kwargs) -> str:
        return f"<{key}>"

    monkeypatch.setattr(execution_runtime_module, "t", _fake_t)

    raw_result = "Skill implemented."
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "read_file",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(side_effect=_publish)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user",
        content="oke lanjut implementasi",
        metadata={
            "runtime_locale": "en",
            "skill_creation_guard": {
                "active": True,
                "stage": "approved",
                "approved": True,
                "request_text": "buat skill baru untuk Threads API",
            },
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    statuses = [m for m in published if (m.metadata or {}).get("type") == "status_update"]
    phases = [m.metadata.get("phase") for m in statuses]
    assert result == raw_result
    assert "executing" in phases
    assert "verified" in phases
    assert "tool" in phases


@pytest.mark.asyncio
async def test_run_agent_loop_direct_process_memory_returns_raw_without_summary_chat():
    raw_result = "ProcessName Id RAM_MB\npython 123 420.0"
    bus = SimpleNamespace(publish_outbound=AsyncMock(return_value=None))
    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "get_process_memory",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=raw_result),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=bus,
        runtime_performance=SimpleNamespace(fast_first_response=True),
    )

    msg = InboundMessage(channel="cli", chat_id="direct", sender_id="user", content="cek ram sekarang")
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == raw_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("get_process_memory", msg)
    loop.provider.chat.assert_not_awaited()
    outbound_texts = [call.args[0].content for call in bus.publish_outbound.await_args_list]
    assert any("wait" in text.lower() or "tunggu" in text.lower() for text in outbound_texts)


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
