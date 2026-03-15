"""Split from tests/agent/loop_core/test_execution_runtime.py to keep test modules below 1000 lines.
Chunk 1: test_run_simple_response_uses_model_chain_fallback .. test_process_tool_calls_blocks_weather_for_non_weather_greeting.
"""

import gc
import warnings
from pathlib import Path
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
from kabot.agent.loop_core.execution_runtime_parts.artifacts import (
    _update_followup_context_from_tool_execution,
)
from kabot.agent.loop_core.execution_runtime_parts.helpers import _extract_single_result_path
from kabot.agent.loop_core.execution_runtime_parts.intent import _tool_call_intent_mismatch_reason
from kabot.agent.loop_core.execution_runtime_parts.intent import _resolve_expected_tool_for_query
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


def test_resolve_expected_tool_for_query_uses_narrow_runtime_wrapper_for_weather_chat():
    loop = SimpleNamespace(
        tools=SimpleNamespace(has=lambda name: name in {"weather", "web_search", "read_file"}),
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cek suhu purwokerto sekarang",
        metadata={},
    )

    expected = _resolve_expected_tool_for_query(loop, msg)

    assert expected is None
    assert msg.metadata.get("_expected_tool_for_guard") is None

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
async def test_run_agent_loop_action_request_skips_planning_when_tool_inference_is_suppressed():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: "read_file"
    loop._plan_task = AsyncMock(return_value="should-not-plan")
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="read-result")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(True, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 2
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (LLMResponse(content="fallback-response"), None),
            (LLMResponse(content="fallback-response"), None),
        ]
    )
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )

    content = "create file .smoke_tmp/smoke_action_request.txt in the workspace containing HALO_KABOT"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "continuity_source": "action_request",
            "suppress_required_tool_inference": True,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert "couldn't verify completion" in result.lower()
    loop._plan_task.assert_not_awaited()
    loop._execute_required_tool_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_grounded_project_inspection_retries_when_model_answers_without_filesystem_tools():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value=None)
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(True, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 2
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (LLMResponse(content="It looks like a modern TypeScript app."), None),
            (LLMResponse(content="Still looks like a Node project."), None),
        ]
    )
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )

    content = "periksa folder openclaw ini dan jelaskan aplikasi apa itu"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "suppress_required_tool_inference": True,
            "requires_grounded_filesystem_inspection": True,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert "grounded project inspection" in result.lower()
    assert loop._call_llm_with_fallback.await_count == 2
    retry_messages = loop._call_llm_with_fallback.await_args_list[1].args[0]
    assert any(
        "list_dir, read_file, find_files, or exec" in str(message.get("content") or "")
        for message in retry_messages
        if isinstance(message, dict)
    )
    loop._execute_required_tool_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_grounded_project_inspection_warms_up_listing_and_representative_files(tmp_path):
    project_dir = tmp_path / "openclaw"
    project_dir.mkdir()
    (project_dir / "README.md").write_text("# OpenClaw\nAgent runtime", encoding="utf-8")
    (project_dir / "package.json").write_text('{"name":"openclaw","private":true}', encoding="utf-8")

    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value=None)
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(True, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda name: name in {"list_dir", "read_file"})
    loop._execute_tool = AsyncMock(
        side_effect=[
            "📁 src\n📄 README.md\n📄 package.json",
            "# OpenClaw\nAgent runtime",
            '{"name":"openclaw","private":true}',
        ]
    )
    loop.max_iterations = 1
    loop._call_llm_with_fallback = AsyncMock(
        return_value=(LLMResponse(content="Ini aplikasi agent runtime."), None)
    )
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )

    content = "periksa folder openclaw ini dan jelaskan aplikasi apa itu"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "suppress_required_tool_inference": True,
            "requires_grounded_filesystem_inspection": True,
            "working_directory": str(project_dir),
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={"working_directory": str(project_dir)}),
    )

    assert result == "Ini aplikasi agent runtime."
    assert loop._execute_tool.await_count == 3
    first_call = loop._execute_tool.await_args_list[0]
    assert first_call.args[0] == "list_dir"
    assert first_call.args[1]["path"] == str(project_dir)
    llm_messages = loop._call_llm_with_fallback.await_args.args[0]
    warmup_message = str(llm_messages[-1].get("content") or "")
    assert "[Grounded Inspection Warmup]" in warmup_message
    assert "📄 README.md" in warmup_message
    assert "[Representative File: README.md]" in warmup_message
    assert "[Representative File: package.json]" in warmup_message


@pytest.mark.asyncio
async def test_run_agent_loop_save_memory_direct_tool_gets_llm_summary_not_raw_tool_text():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: "save_memory"
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(
        return_value="[OK] preference saved: User prefers to be called Maha Raja..."
    )
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(True, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda name: name == "save_memory")
    loop.max_iterations = 1
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, tool_calls=None, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})},
        ]
    )
    loop.provider = SimpleNamespace(
        chat=AsyncMock(return_value=LLMResponse(content="Siap, Maha Raja. Mulai sekarang aku panggil begitu."))
    )

    content = "setiap kali kamu balas harus panggil aku Maha Raja ingat itu"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "CHAT",
            "runtime_locale": "id",
            "required_tool": "save_memory",
            "required_tool_query": content,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert result == "Siap, Maha Raja. Mulai sekarang aku panggil begitu."
    loop._execute_required_tool_fallback.assert_awaited_once()
    loop.provider.chat.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_agent_loop_coding_request_skips_external_planner_and_rejects_text_only_completion_without_execution():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value="1. build page\n2. verify output")
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="unused")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 2
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (LLMResponse(content="Saya akan kerjakan sekarang."), None),
            (LLMResponse(content="Sudah jadi."), None),
        ]
    )

    content = "YA"
    effective_content = (
        "YA\n\n[Committed Action Context]\n"
        "buat website landing page KAIDUT tema dark style crypto lalu screenshot dan kirim ke chat ini\n\n"
        "[Coding Build Note]\nTreat this as a coding task."
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": effective_content,
            "route_profile": "CODING",
            "runtime_locale": "id",
            "continuity_source": "committed_coding_action",
            "requires_message_delivery": True,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert "couldn't verify completion" in result.lower()
    loop._plan_task.assert_not_awaited()
    second_messages = loop._call_llm_with_fallback.await_args_list[1].args[0]
    assert "requires real execution with tools or approved skills" in second_messages[-1]["content"].lower()
    assert not any("[SYSTEM PLAN]" in str(message.get("content", "")) for message in second_messages)


@pytest.mark.asyncio
async def test_run_agent_loop_action_request_retries_and_rejects_text_only_completion_without_tool_evidence():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="unused")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 2
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (LLMResponse(content="smoke_action_request.txt"), None),
            (LLMResponse(content="smoke_action_request.txt"), None),
        ]
    )

    content = "create file .smoke_tmp/smoke_action_request.txt in the workspace containing HALO_KABOT"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "continuity_source": "action_request",
            "suppress_required_tool_inference": True,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert "couldn't verify completion" in result.lower()
    assert loop._call_llm_with_fallback.await_count == 2
    second_messages = loop._call_llm_with_fallback.await_args_list[1].args[0]
    assert "requires real execution with tools or approved skills" in second_messages[-1]["content"].lower()
    loop._execute_required_tool_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_approved_skill_workflow_retries_and_rejects_text_only_completion_without_execution():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="unused")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 2
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (LLMResponse(content="Aku lanjut implementasi sekarang."), None),
            (LLMResponse(content="Skill sudah jadi."), None),
        ]
    )

    content = "approve, eksekusi"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "forced_skill_names": ["skill-creator"],
            "requires_real_skill_execution": True,
            "skill_creation_guard": {
                "active": True,
                "stage": "approved",
                "approved": True,
                "request_text": "buat skill saham via Yahoo Finance",
            },
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert "couldn't verify completion" in result.lower()
    assert loop._call_llm_with_fallback.await_count == 2
    second_messages = loop._call_llm_with_fallback.await_args_list[1].args[0]
    assert "requires real execution with tools or approved skills" in second_messages[-1]["content"].lower()
    loop._execute_required_tool_fallback.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_existing_skill_runtime_followup_uses_server_monitor_fallback_instead_of_generic_error():
    loop = _make_loop()
    raw_result = "### Server Resource Monitor\n**CPU Load:** 12.0%\n**RAM:** 2.00 / 8.00 GB"
    summarized_result = "Status server sudah dicek: CPU 12.0%, RAM 2.00 / 8.00 GB."
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value=raw_result)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content=summarized_result))
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda name: name == "server_monitor")
    loop.max_iterations = 2
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content},
        ]
    )
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (LLMResponse(content="Saya akan lanjut cek server."), None),
            (LLMResponse(content="Saya akan lanjut cek server."), None),
        ]
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="lanjut",
        metadata={
            "effective_content": "lanjut",
            "route_profile": "CHAT",
            "runtime_locale": "id",
            "continuity_source": "existing_skill_followup",
            "required_tool": "server_monitor",
            "required_tool_query": "cek runtime server saat ini",
            "forced_skill_names": ["cek-runtime-vps"],
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert result == summarized_result
    loop._execute_required_tool_fallback.assert_awaited_once_with("server_monitor", msg)
    loop.provider.chat.assert_awaited_once()
    summary_messages = loop.provider.chat.await_args.kwargs["messages"]
    assert any(raw_result in str(item.get("content") or "") for item in summary_messages)
    assert "couldn't verify completion" not in result.lower()


@pytest.mark.asyncio
async def test_run_agent_loop_action_request_retries_when_explicit_artifact_path_still_missing_after_tool_calls(tmp_path):
    loop = _make_loop()
    loop.workspace = tmp_path
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="unused")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 3
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, tool_calls=None, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})},
        ]
    )

    async def _process_tool_calls(_msg, messages, _response, _session):
        return [*messages, {"role": "tool", "content": "write failed"}]

    loop._process_tool_calls = AsyncMock(side_effect=_process_tool_calls)
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (
                LLMResponse(
                    content="writing",
                    tool_calls=[
                        ToolCallRequest(
                            id="call_write",
                            name="write_file",
                            arguments={
                                "path": ".smoke_tmp/smoke_action_request.txt",
                                "content": "HALO_KABOT",
                            },
                        )
                    ],
                ),
                None,
            ),
            (LLMResponse(content="smoke_action_request.txt"), None),
            (LLMResponse(content="smoke_action_request.txt"), None),
        ]
    )

    content = "create file .smoke_tmp/smoke_action_request.txt in the workspace containing HALO_KABOT"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "continuity_source": "action_request",
            "suppress_required_tool_inference": True,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert "target file still does not exist" in result.lower() or "requested artifact" in result.lower()
    assert loop._call_llm_with_fallback.await_count == 3
    third_messages = loop._call_llm_with_fallback.await_args_list[2].args[0]
    assert "still does not exist" in third_messages[-1]["content"].lower()


@pytest.mark.asyncio
async def test_run_agent_loop_action_request_retries_and_rejects_delivery_without_message_evidence():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._execute_required_tool_fallback = AsyncMock(return_value="unused")
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 3
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, tool_calls=None, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})},
        ]
    )

    async def _process_tool_calls(_msg, messages, _response, _session):
        _msg.metadata["executed_tools"] = ["find_files"]
        return [*messages, {"role": "tool", "content": "FILE report.pdf"}]

    loop._process_tool_calls = AsyncMock(side_effect=_process_tool_calls)
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (
                LLMResponse(
                    content="searching",
                    tool_calls=[ToolCallRequest(id="call_find", name="find_files", arguments={"query": "report.pdf"})],
                ),
                None,
            ),
            (LLMResponse(content="Sudah saya kirim."), None),
            (LLMResponse(content="Sudah saya kirim."), None),
        ]
    )

    content = "cari file report.pdf lalu kirim ke chat ini"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "continuity_source": "action_request",
            "requires_message_delivery": True,
        },
    )

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=SimpleNamespace(metadata={}),
    )

    assert "couldn't verify delivery" in result.lower() or "won't claim the file was sent" in result.lower()
    assert loop._call_llm_with_fallback.await_count == 3
    third_messages = loop._call_llm_with_fallback.await_args_list[2].args[0]
    assert "message" in third_messages[-1]["content"].lower()
    assert "file" in third_messages[-1]["content"].lower()


@pytest.mark.asyncio
async def test_run_agent_loop_action_request_recovers_delivery_via_direct_message_fallback():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda _name: False)
    loop.max_iterations = 3
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, tool_calls=None, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})},
        ]
    )

    async def _process_tool_calls(_msg, messages, _response, _session):
        _msg.metadata["executed_tools"] = ["find_files"]
        _session.metadata["last_tool_context"] = {
            "tool": "find_files",
            "source": "report.pdf",
            "path": r"C:\tmp\report.pdf",
            "updated_at": 0.0,
        }
        return [*messages, {"role": "tool", "content": r"FILE C:\tmp\report.pdf"}]

    loop._process_tool_calls = AsyncMock(side_effect=_process_tool_calls)

    async def _fallback(tool_name, _msg):
        if tool_name == "message":
            return "Message sent to telegram:chat-1"
        return "unused"

    loop._execute_required_tool_fallback = AsyncMock(side_effect=_fallback)
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (
                LLMResponse(
                    content="searching",
                    tool_calls=[ToolCallRequest(id="call_find", name="find_files", arguments={"query": "report.pdf"})],
                ),
                None,
            ),
            (LLMResponse(content="Sudah saya kirim."), None),
        ]
    )

    content = "cari file report.pdf lalu kirim ke chat ini"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "continuity_source": "action_request",
            "requires_message_delivery": True,
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=session,
    )

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("message_delivery_verified") is True
    assert "message" in msg.metadata.get("executed_tools", [])
    loop._execute_required_tool_fallback.assert_any_await("message", msg)


@pytest.mark.asyncio
async def test_run_agent_loop_coding_request_recovers_delivery_via_direct_message_fallback():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value="plan")
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda name: name == "message")
    loop.max_iterations = 3
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, tool_calls=None, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})},
        ]
    )

    async def _process_tool_calls(_msg, messages, _response, _session):
        _msg.metadata["executed_tools"] = ["write_file"]
        _session.metadata["last_tool_context"] = {
            "tool": "write_file",
            "source": "landing page",
            "path": r"C:\tmp\kaidut-landing-ss.png",
            "updated_at": 0.0,
        }
        return [*messages, {"role": "tool", "content": r"Screenshot saved: C:\tmp\kaidut-landing-ss.png"}]

    loop._process_tool_calls = AsyncMock(side_effect=_process_tool_calls)

    async def _fallback(tool_name, _msg):
        if tool_name == "message":
            return "Message sent to telegram:chat-1"
        return "unused"

    loop._execute_required_tool_fallback = AsyncMock(side_effect=_fallback)
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (
                LLMResponse(
                    content="building",
                    tool_calls=[
                        ToolCallRequest(
                            id="call_write",
                            name="write_file",
                            arguments={"path": "kaidut-landing.html", "content": "<html></html>"},
                        )
                    ],
                ),
                None,
            ),
            (LLMResponse(content="Sudah saya kirim."), None),
        ]
    )

    content = "YA"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": (
                "YA\n\n[Committed Action Context]\n"
                "buat website landing page KAIDUT tema dark style crypto lalu screenshot dan kirim ke chat ini"
            ),
            "route_profile": "CODING",
            "runtime_locale": "id",
            "continuity_source": "committed_coding_action",
            "requires_message_delivery": True,
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=session,
    )

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("message_delivery_verified") is True
    assert "message" in msg.metadata.get("executed_tools", [])
    loop._execute_required_tool_fallback.assert_any_await("message", msg)


@pytest.mark.asyncio
async def test_run_agent_loop_action_request_recovers_delivery_from_generic_tool_path_context():
    loop = _make_loop()
    loop._required_tool_for_query = lambda _text: None
    loop._plan_task = AsyncMock(return_value=None)
    loop._apply_think_mode = lambda messages, _session: messages
    loop._is_weak_model = lambda _model: False
    loop._self_evaluate = lambda _question, _response: (True, None)
    loop._critic_evaluate = AsyncMock(return_value=(10, ""))
    loop._review_tool_output = AsyncMock(return_value=None)
    loop._get_last_tool_context = lambda _session: None
    loop.tools = SimpleNamespace(has=lambda name: name in {"message", "mcp__nanobanana__video"})
    loop.max_iterations = 3
    loop.context = SimpleNamespace(
        add_assistant_message=lambda messages, content, tool_calls=None, reasoning_content=None: [
            *messages,
            {"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})},
        ]
    )

    async def _process_tool_calls(_msg, messages, _response, _session):
        _msg.metadata["executed_tools"] = ["mcp__nanobanana__video"]
        _session.metadata["last_tool_context"] = {
            "tool": "mcp__nanobanana__video",
            "source": "buat video promo",
            "path": r"C:\tmp\promo.mp4",
            "updated_at": 0.0,
        }
        return [*messages, {"role": "tool", "content": r"Video generated: C:\tmp\promo.mp4"}]

    loop._process_tool_calls = AsyncMock(side_effect=_process_tool_calls)

    async def _fallback(tool_name, _msg):
        if tool_name == "message":
            return "Message sent to telegram:chat-1"
        return "unused"

    loop._execute_required_tool_fallback = AsyncMock(side_effect=_fallback)
    loop._call_llm_with_fallback = AsyncMock(
        side_effect=[
            (
                LLMResponse(
                    content="rendering",
                    tool_calls=[
                        ToolCallRequest(
                            id="call_video",
                            name="mcp__nanobanana__video",
                            arguments={"prompt": "buat video promo"},
                        )
                    ],
                ),
                None,
            ),
            (LLMResponse(content="Sudah saya kirim."), None),
        ]
    )

    content = "buat video promo lalu kirim ke chat ini"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={
            "effective_content": content,
            "route_profile": "GENERAL",
            "runtime_locale": "id",
            "continuity_source": "action_request",
            "requires_message_delivery": True,
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        session=session,
    )

    assert result == "Message sent to telegram:chat-1"
    assert msg.metadata.get("message_delivery_verified") is True
    assert "message" in msg.metadata.get("executed_tools", [])
    loop._execute_required_tool_fallback.assert_any_await("message", msg)

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
async def test_process_tool_calls_marks_message_delivery_evidence(tmp_path):
    tool_executor = AsyncMock(return_value="Message sent to telegram:8086")
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
        content=r"send file C:\Users\Arvy Kairi\Desktop\report.pdf to this chat",
        metadata={},
    )
    response = LLMResponse(
        content="sending",
        tool_calls=[
            ToolCallRequest(
                id="call_message",
                name="message",
                arguments={"content": "Here is the file.", "files": [r"C:\Users\Arvy Kairi\Desktop\report.pdf"]},
            )
        ],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    assert msg.metadata.get("executed_tools") == ["message"]
    assert msg.metadata.get("message_delivery_verified") is True
    evidence = msg.metadata.get("completion_evidence")
    assert evidence["executed_tools"] == ["message"]
    assert evidence["artifact_paths"] == [r"C:\Users\Arvy Kairi\Desktop\report.pdf"]
    assert evidence["artifact_verified"] is True
    assert evidence["delivery_verified"] is True


@pytest.mark.asyncio
async def test_process_tool_calls_captures_generic_tool_result_path_for_delivery_reuse(tmp_path):
    tool_executor = AsyncMock(return_value=r"Video generated: C:\tmp\promo.mp4")
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
        content="buat video promo lalu kirim ke chat ini",
        metadata={"requires_message_delivery": True},
    )
    response = LLMResponse(
        content="rendering",
        tool_calls=[
            ToolCallRequest(
                id="call_video",
                name="mcp__nanobanana__video",
                arguments={"prompt": "buat video promo"},
            )
        ],
    )
    session = SimpleNamespace(metadata={})

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=session,
    )

    last_tool_context = session.metadata.get("last_tool_context")
    assert isinstance(last_tool_context, dict)
    assert last_tool_context.get("path") == r"C:\tmp\promo.mp4"
    assert msg.metadata.get("executed_tools") == ["mcp__nanobanana__video"]


def test_extract_single_result_path_reads_relative_artifact_path_from_structured_result():
    result = {
        "artifacts": [
            {"path": "outputs/promo.mp4", "mime_type": "video/mp4"},
            {"path": "outputs/promo-alt.mp4", "mime_type": "video/mp4"},
        ]
    }

    assert _extract_single_result_path("mcp__nanobanana__video", {}, result) == "outputs/promo.mp4"


def test_extract_single_result_path_reads_artifact_path_from_exec_command_arguments():
    command = (
        "python -c \"from playwright.sync_api import sync_playwright; "
        "page.screenshot(path='C:/tmp/kaidut-landing-ss.png', full_page=True)\""
    )

    assert (
        _extract_single_result_path("exec", {"command": command}, "OK")
        == "C:/tmp/kaidut-landing-ss.png"
    )


def test_extract_single_result_path_prefers_requested_directory_for_list_dir_results():
    result = "📁 bot\n📄 note.txt"

    assert (
        _extract_single_result_path("list_dir", {"path": "/tmp/workspace/Desktop"}, result)
        == "/tmp/workspace/Desktop"
    )


def test_update_followup_context_list_dir_keeps_working_directory_canonical_without_redundant_breadcrumb(tmp_path):
    target_dir = tmp_path / "workspace" / "docs"
    target_dir.mkdir(parents=True, exist_ok=True)
    session = SimpleNamespace(metadata={})

    _update_followup_context_from_tool_execution(
        session,
        tool_name="list_dir",
        tool_args={"path": str(target_dir)},
        fallback_source=f"open {target_dir}",
        tool_result="README.md",
    )

    assert session.metadata.get("working_directory") == str(target_dir.resolve())
    assert session.metadata.get("last_navigated_path") is None


def test_extract_single_result_path_reads_tilde_prefixed_artifact_path_from_exec_output():
    result = "Screenshot saved to ~/Desktop/kabot-shot.png"

    assert (
        _extract_single_result_path("exec", {}, result)
        == "~/Desktop/kabot-shot.png"
    )


@pytest.mark.asyncio
async def test_process_tool_calls_expands_browser_screenshot_result_path_for_delivery_reuse(
    tmp_path,
    monkeypatch,
):
    fake_home = tmp_path / "home"
    screenshot_path = fake_home / "Desktop" / "kabot-shot.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path.write_bytes(b"png")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))

    tool_executor = AsyncMock(return_value="Screenshot saved to ~/Desktop/kabot-shot.png")
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
        content="take a screenshot and send it to chat",
        metadata={"requires_message_delivery": True},
    )
    response = LLMResponse(
        content="capturing",
        tool_calls=[
            ToolCallRequest(
                id="call_browser",
                name="browser",
                arguments={"action": "screenshot"},
            )
        ],
    )
    session = SimpleNamespace(metadata={})

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=session,
    )

    last_tool_context = session.metadata.get("last_tool_context")
    assert isinstance(last_tool_context, dict)
    assert Path(str(last_tool_context.get("path"))).resolve() == screenshot_path.resolve()
    assert session.metadata.get("working_directory") == str(screenshot_path.parent.resolve())
    assert msg.metadata.get("executed_tools") == ["browser"]


@pytest.mark.asyncio
async def test_process_tool_calls_captures_relative_structured_tool_result_path_for_delivery_reuse(tmp_path):
    tool_executor = AsyncMock(
        return_value={
            "artifacts": [
                {"path": "outputs/promo.mp4", "mime_type": "video/mp4"},
                {"path": "outputs/promo-poster.jpg", "mime_type": "image/jpeg"},
            ]
        }
    )
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
        content="buat video promo lalu kirim ke chat ini",
        metadata={"requires_message_delivery": True},
    )
    response = LLMResponse(
        content="rendering",
        tool_calls=[
            ToolCallRequest(
                id="call_video",
                name="mcp__nanobanana__video",
                arguments={"prompt": "buat video promo"},
            )
        ],
    )
    session = SimpleNamespace(metadata={})

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=session,
    )

    last_tool_context = session.metadata.get("last_tool_context")
    assert isinstance(last_tool_context, dict)
    assert last_tool_context.get("path") == "outputs/promo.mp4"
    assert msg.metadata.get("executed_tools") == ["mcp__nanobanana__video"]


@pytest.mark.asyncio
async def test_process_tool_calls_prefers_working_directory_over_stale_last_delivery_for_relative_artifacts(tmp_path):
    working_dir = tmp_path / "active-workspace"
    artifact_path = working_dir / "outputs" / "promo.mp4"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b"video")

    stale_dir = tmp_path / "stale-delivery"
    stale_dir.mkdir(parents=True, exist_ok=True)
    stale_file = stale_dir / "old-report.txt"
    stale_file.write_text("old", encoding="utf-8")

    tool_executor = AsyncMock(
        return_value={
            "artifacts": [
                {"path": "outputs/promo.mp4", "mime_type": "video/mp4"},
            ]
        }
    )
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
        content="render a promo video",
        metadata={"requires_message_delivery": True},
    )
    response = LLMResponse(
        content="rendering",
        tool_calls=[
            ToolCallRequest(
                id="call_video",
                name="mcp__nanobanana__video",
                arguments={"prompt": "render a promo video"},
            )
        ],
    )
    session = SimpleNamespace(
        metadata={
            "working_directory": str(working_dir.resolve()),
            "last_delivery_path": str(stale_file.resolve()),
        }
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=session,
    )

    last_tool_context = session.metadata.get("last_tool_context")
    assert isinstance(last_tool_context, dict)
    assert Path(str(last_tool_context.get("path"))).resolve() == artifact_path.resolve()
    assert session.metadata.get("working_directory") == str(artifact_path.parent.resolve())


@pytest.mark.asyncio
async def test_process_tool_calls_prefers_last_tool_context_path_over_stale_last_delivery_for_relative_artifacts(tmp_path):
    active_dir = tmp_path / "active-context"
    artifact_path = active_dir / "outputs" / "promo.mp4"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_bytes(b"video")

    stale_dir = tmp_path / "stale-delivery"
    stale_dir.mkdir(parents=True, exist_ok=True)
    stale_file = stale_dir / "old-report.txt"
    stale_file.write_text("old", encoding="utf-8")

    tool_executor = AsyncMock(
        return_value={
            "artifacts": [
                {"path": "outputs/promo.mp4", "mime_type": "video/mp4"},
            ]
        }
    )
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
        content="render a promo video",
        metadata={"requires_message_delivery": True},
    )
    response = LLMResponse(
        content="rendering",
        tool_calls=[
            ToolCallRequest(
                id="call_video",
                name="mcp__nanobanana__video",
                arguments={"prompt": "render a promo video"},
            )
        ],
    )
    session = SimpleNamespace(
        metadata={
            "last_tool_context": {
                "tool": "list_dir",
                "path": str(active_dir.resolve()),
            },
            "last_delivery_path": str(stale_file.resolve()),
        }
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=session,
    )

    last_tool_context = session.metadata.get("last_tool_context")
    assert isinstance(last_tool_context, dict)
    assert Path(str(last_tool_context.get("path"))).resolve() == artifact_path.resolve()
    assert session.metadata.get("working_directory") == str(artifact_path.parent.resolve())


@pytest.mark.asyncio
async def test_process_tool_calls_allows_find_files_for_find_then_send_workflow(tmp_path):
    tool_executor = AsyncMock(return_value="FILE C:/tmp/report.pdf")
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
        content="cari file report.pdf lalu kirim ke chat ini",
        metadata={"requires_message_delivery": True, "continuity_source": "action_request"},
    )
    response = LLMResponse(
        content="searching",
        tool_calls=[
            ToolCallRequest(
                id="call_find",
                name="find_files",
                arguments={"query": "report.pdf"},
            )
        ],
    )

    updated = await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once()
    assert any(
        item.get("role") == "tool" and item.get("tool_call_id") == "call_find"
        for item in updated
    )


@pytest.mark.asyncio
async def test_process_tool_calls_allows_message_for_find_then_send_workflow(tmp_path):
    tool_executor = AsyncMock(return_value="Message sent to telegram:8086")
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
        content="cari file report.pdf lalu kirim ke chat ini",
        metadata={"requires_message_delivery": True, "continuity_source": "action_request"},
    )
    response = LLMResponse(
        content="sending",
        tool_calls=[
            ToolCallRequest(
                id="call_message",
                name="message",
                arguments={"content": "Ini filenya.", "files": [r"C:\tmp\report.pdf"]},
            )
        ],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once()
    assert msg.metadata.get("executed_tools") == ["message"]
    assert msg.metadata.get("message_delivery_verified") is True

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

    msg = InboundMessage(channel="telegram", chat_id="8086", sender_id="user", content="check weather")
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
        content="find latest Iran war news 2026 now",
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
async def test_process_tool_calls_allows_read_file_for_coding_request_followup_without_explicit_payload(tmp_path):
    tool_executor = AsyncMock(return_value="<html>KAIDUT</html>")
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
        content="YA",
        metadata={
            "effective_content": (
                "YA\n\n[Committed Action Context]\n"
                "buat website landing page KAIDUT tema dark style crypto lalu screenshot dan kirim ke chat ini"
            ),
            "route_profile": "CODING",
            "continuity_source": "committed_coding_action",
            "requires_message_delivery": True,
        },
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[ToolCallRequest(id="call_read", name="read_file", arguments={"path": "landing/index.html"})],
    )

    await process_tool_calls(
        loop,
        msg,
        [{"role": "user", "content": msg.content}],
        response,
        session=SimpleNamespace(metadata={}),
    )

    tool_executor.assert_awaited_once_with("read_file", {"path": "landing/index.html"})

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


def test_tool_call_intent_mismatch_allows_message_send_without_explicit_path_when_session_has_delivery_context():
    session = SimpleNamespace(metadata={"last_delivery_path": r"C:\\Users\\Arvy Kairi\\Desktop\\bot\\tes.md"})
    loop = SimpleNamespace(
        tools=SimpleNamespace(has=lambda name: name == "message"),
        sessions=SimpleNamespace(get_or_create=lambda _key: session),
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="send it now",
        metadata={},
    )

    reason = _tool_call_intent_mismatch_reason(loop, msg, "message")

    assert reason is None


def test_tool_call_intent_mismatch_allows_message_send_without_explicit_path_when_session_has_delivery_route():
    session = SimpleNamespace(
        metadata={
            "delivery_route": {
                "channel": "telegram",
                "chat_id": "chat-1",
            }
        }
    )
    loop = SimpleNamespace(
        tools=SimpleNamespace(has=lambda name: name == "message"),
        sessions=SimpleNamespace(get_or_create=lambda _key: session),
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="send it here",
        metadata={},
    )

    reason = _tool_call_intent_mismatch_reason(loop, msg, "message")

    assert reason is None


def test_tool_call_intent_mismatch_allows_message_send_without_explicit_path_when_active_working_directory_exists():
    session = SimpleNamespace(metadata={})
    loop = SimpleNamespace(
        tools=SimpleNamespace(has=lambda name: name == "message"),
        sessions=SimpleNamespace(get_or_create=lambda _key: session),
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="send it here",
        metadata={"working_directory": r"C:\\Users\\Arvy Kairi\\Desktop\\bot"},
    )

    reason = _tool_call_intent_mismatch_reason(loop, msg, "message")

    assert reason is None


def test_tool_call_intent_mismatch_rejects_bare_send_when_only_active_last_delivery_path_exists():
    session = SimpleNamespace(metadata={})
    loop = SimpleNamespace(
        tools=SimpleNamespace(has=lambda name: name == "message"),
        sessions=SimpleNamespace(get_or_create=lambda _key: session),
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="send it",
        metadata={"last_delivery_path": r"C:\\Users\\Arvy Kairi\\Desktop\\bot\\tes.md"},
    )

    reason = _tool_call_intent_mismatch_reason(loop, msg, "message")

    assert reason == "low-information turn"


def test_tool_call_intent_mismatch_blocks_browser_for_headless_live_lookup():
    session = SimpleNamespace(metadata={})
    loop = SimpleNamespace(
        tools=SimpleNamespace(has=lambda name: name in {"web_search", "web_fetch"}),
        sessions=SimpleNamespace(get_or_create=lambda _key: session),
    )
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="check bbca stock price now",
        metadata={},
    )

    reason = _tool_call_intent_mismatch_reason(loop, msg, "browser")

    assert reason == "prefer web_search/web_fetch for headless factual lookup"
