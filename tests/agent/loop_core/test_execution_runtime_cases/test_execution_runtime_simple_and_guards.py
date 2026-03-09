"""Split from tests/agent/loop_core/test_execution_runtime.py to keep test modules below 1000 lines.
Chunk 1: test_run_simple_response_uses_model_chain_fallback .. test_process_tool_calls_blocks_weather_for_non_weather_greeting.
"""

import gc
import warnings
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
        include_tools_initial=False,
    )
    loop.provider.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_call_llm_with_fallback_can_start_text_only_for_simple_response():
    provider = SimpleNamespace(
        chat=AsyncMock(return_value=LLMResponse(content="text-only-ok")),
    )
    loop = SimpleNamespace(
        provider=provider,
        tools=SimpleNamespace(get_definitions=lambda: [{"name": "weather"}]),
        auth_rotation=None,
        resilience=SimpleNamespace(handle_error=AsyncMock(), on_success=lambda: None),
        runtime_resilience=SimpleNamespace(max_model_attempts_per_turn=4, strict_error_classification=True),
        last_model_used=None,
        last_fallback_used=False,
        last_model_chain=[],
    )

    response, error = await call_llm_with_fallback(
        loop,
        [{"role": "user", "content": "hari apa sekarang?"}],
        ["openai-codex/gpt-5.3-codex"],
        include_tools_initial=False,
    )

    assert error is None
    assert response is not None
    assert response.content == "text-only-ok"
    provider.chat.assert_awaited_once()
    assert "tools" not in provider.chat.await_args.kwargs

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


def test_apply_response_quota_usage_ignores_asyncmock_usage_without_warning():
    loop = SimpleNamespace()
    response = SimpleNamespace(usage=AsyncMock(), model="openai-codex/gpt-5.3-codex")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        execution_runtime_module._apply_response_quota_usage(loop, response)
        del response
        gc.collect()

    runtime_warnings = [item for item in caught if issubclass(item.category, RuntimeWarning)]
    assert runtime_warnings == []
    assert not hasattr(loop, "last_usage")

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
async def test_run_agent_loop_meta_feedback_with_live_marker_respects_suppressed_tool_inference():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="web-result")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(True, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda name: name == "web_search")
    loop.max_iterations = 1
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )

    content = "sekarang senin woi astaga kenapa ga disimpan di memory mu"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "CHAT",
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
