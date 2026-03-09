"""Split from tests/agent/loop_core/test_execution_runtime.py to keep test modules below 1000 lines.
Chunk 2: test_process_tool_calls_blocks_image_tool_for_non_image_intent .. test_run_agent_loop_direct_process_memory_returns_raw_without_summary_chat.
"""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import kabot.agent.loop_core.execution_runtime as execution_runtime_module
from kabot.agent.context import ContextBuilder
from kabot.agent.loop_core.execution_runtime import (
    call_llm_with_fallback,
    process_tool_calls,
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
