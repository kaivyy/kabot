from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kabot.agent.context import ContextBuilder
from kabot.agent.loop_core.execution_runtime import process_tool_calls
from kabot.agent.loop_core.execution_runtime_parts.agent_loop import run_agent_loop
from kabot.agent.loop_core.execution_runtime_parts.intent import (
    _looks_like_live_research_query,
    _query_has_explicit_payload_for_tool,
    _should_defer_live_research_latch_to_skill,
)
from kabot.bus.events import InboundMessage
from kabot.providers.base import LLMResponse, ToolCallRequest


@pytest.mark.asyncio
async def test_process_tool_calls_blocks_web_search_for_general_knowledge_explain_query(tmp_path):
    tool_executor = AsyncMock(return_value="search result")
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
        content="can you explain about earth? what is earth or something, everything you know about earth",
    )
    response = LLMResponse(
        content="tool-run",
        tool_calls=[
            ToolCallRequest(
                id="call_web",
                name="web_search",
                arguments={"query": "earth planet explanation"},
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

    assert tool_executor.await_count == 0
    tool_messages = [
        item
        for item in updated
        if item.get("role") == "tool" and item.get("tool_call_id") == "call_web"
    ]
    assert tool_messages
    assert "TOOL_CALL_BLOCKED_INTENT_MISMATCH" in str(tool_messages[-1].get("content") or "")


def test_live_research_latch_yields_to_explicit_external_skill_request():
    loop = SimpleNamespace(
        context=SimpleNamespace(
            skills=SimpleNamespace(
                has_preferred_external_skill_match=lambda text, profile="GENERAL": "bbca" in str(text).lower()
            )
        )
    )

    assert _should_defer_live_research_latch_to_skill(
        loop,
        "pakai skill yahoo-finance-stock untuk cek harga saham bbca bri mandiri adaro sekarang",
        profile="GENERAL",
    )


def test_live_research_latch_yields_to_grounded_external_skill_match_even_without_explicit_request():
    loop = SimpleNamespace(
        context=SimpleNamespace(
            skills=SimpleNamespace(
                has_preferred_external_skill_match=lambda text, profile="GENERAL": "bbca" in str(text).lower()
            )
        )
    )

    assert _should_defer_live_research_latch_to_skill(
        loop,
        "cek harga saham bbca bri mandiri adaro sekarang",
        profile="GENERAL",
    )


def test_live_research_latch_yields_to_active_external_skill_lane_from_session_metadata():
    loop = SimpleNamespace(
        context=SimpleNamespace(
            skills=SimpleNamespace(
                has_preferred_external_skill_match=lambda text, profile="GENERAL": "bbca" in str(text).lower()
            )
        ),
    )

    assert _should_defer_live_research_latch_to_skill(
        loop,
        "cek harga saham bbca bri mandiri adaro sekarang",
        profile="GENERAL",
        session_metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
        },
    )


def test_live_research_latch_does_not_leak_stale_session_skill_lane_into_unrelated_topic():
    loop = SimpleNamespace(
        context=SimpleNamespace(
            skills=SimpleNamespace(
                has_preferred_external_skill_match=lambda text, profile="GENERAL": "bbca" in str(text).lower()
            )
        ),
    )

    assert not _should_defer_live_research_latch_to_skill(
        loop,
        "latest news about earth today",
        profile="RESEARCH",
        session_metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
        },
    )


def test_live_research_latch_yields_to_active_external_skill_lane_from_message_metadata():
    loop = SimpleNamespace(
        context=SimpleNamespace(
            skills=SimpleNamespace(
                has_preferred_external_skill_match=lambda text, profile="GENERAL": "bbca" in str(text).lower()
            )
        ),
    )

    assert _should_defer_live_research_latch_to_skill(
        loop,
        "cek harga saham bbca bri mandiri adaro sekarang",
        profile="GENERAL",
        message_metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
        },
    )


def test_live_research_query_helper_is_english_first():
    assert _looks_like_live_research_query("latest news about earth today") is True
    assert _looks_like_live_research_query("berita terbaru bumi sekarang") is False


def test_query_has_explicit_payload_for_legacy_finance_tools_requires_exact_entities():
    assert _query_has_explicit_payload_for_tool(
        "stock",
        "cek harga saham bca bri mandiri adaro sekarang",
    ) is False
    assert _query_has_explicit_payload_for_tool(
        "stock_analysis",
        "how is apple stock trending lately",
    ) is False
    assert _query_has_explicit_payload_for_tool(
        "stock",
        "BBCA.JK BBRI.JK BMRI.JK ADRO.JK",
    ) is True
    assert _query_has_explicit_payload_for_tool(
        "stock_analysis",
        "AAPL trend 3 months",
    ) is True


@pytest.mark.asyncio
async def test_run_agent_loop_demotes_web_search_setup_hint_to_web_fetch_for_direct_page_request(
    tmp_path,
):
    search_hint = (
        "web_search needs a search API key. Configure BRAVE_API_KEY, "
        "PERPLEXITY_API_KEY, XAI_API_KEY, or KIMI_API_KEY/MOONSHOT_API_KEY "
        "in tools.web.search or your environment. For direct page fetches, use web_fetch."
    )
    fetch_result = "HTTP 200\n\n[EXTERNAL_CONTENT]\nExample Domain\n[/EXTERNAL_CONTENT]"
    first_response = LLMResponse(
        content="checking",
        tool_calls=[
            ToolCallRequest(
                id="call_search",
                name="web_search",
                arguments={"query": "fetch https://example.com and summarize the page"},
            )
        ],
    )

    execute_mock = AsyncMock(side_effect=[search_hint, fetch_result])
    loop = SimpleNamespace(
        max_iterations=3,
        context_guard=SimpleNamespace(check_overflow=lambda _messages, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _is_weak_model=lambda _model: False,
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(return_value=(first_response, None)),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _execute_required_tool_fallback=AsyncMock(return_value=None),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(
            get=lambda _name: None,
            execute=execute_mock,
            has=lambda name: name in {"web_search", "web_fetch"},
        ),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        bus=SimpleNamespace(
            publish_outbound=AsyncMock(return_value=None),
            take_pending_inbound_for_session=lambda *_args, **_kwargs: [],
        ),
        exec_auto_approve=False,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
    )

    async def _process_tool_calls(_msg, messages, response, _session):
        return await process_tool_calls(loop, _msg, messages, response, _session)

    loop._process_tool_calls = AsyncMock(side_effect=_process_tool_calls)

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="fetch https://example.com and summarize the page",
        metadata={"turn_category": "action"},
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert "Example Domain" in result
    assert execute_mock.await_count == 2
    assert execute_mock.await_args_list[0].args[0] == "web_search"
    assert execute_mock.await_args_list[1].args[0] == "web_fetch"


@pytest.mark.asyncio
async def test_run_agent_loop_direct_web_search_selected_source_auto_fetches_matching_result():
    search_result = (
        "Results for: harga saham BBCA sekarang site:finance.yahoo.com\n\n"
        "1. PT Bank Central Asia Tbk (BBCA.JK)\n"
        "   https://finance.yahoo.com/quote/BBCA.JK\n"
        "   Snapshot quote page"
    )
    fetch_result = "HTTP 200\n\n[EXTERNAL_CONTENT]\nBBCA.JK 9,125.00\n[/EXTERNAL_CONTENT]"
    execute_mock = AsyncMock(return_value=fetch_result)

    loop = SimpleNamespace(
        max_iterations=1,
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: "web_search",
        _is_weak_model=lambda _model: False,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _execute_required_tool_fallback=AsyncMock(return_value=search_result),
        tools=SimpleNamespace(
            execute=execute_mock,
            has=lambda name: name in {"web_search", "web_fetch"},
        ),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="should-not-be-used"))),
        bus=SimpleNamespace(publish_outbound=AsyncMock(return_value=None)),
    )

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="yahoo finance",
        metadata={
            "required_tool": "web_search",
            "required_tool_query": "harga saham BBCA sekarang site:finance.yahoo.com",
            "turn_category": "action",
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert "BBCA.JK 9,125.00" in result
    loop._execute_required_tool_fallback.assert_awaited_once_with("web_search", msg)
    execute_mock.assert_awaited_once_with(
        "web_fetch",
        {
            "url": "https://finance.yahoo.com/quote/BBCA.JK",
            "extract_mode": "markdown",
        },
    )


@pytest.mark.asyncio
async def test_run_agent_loop_direct_web_search_setup_hint_continues_with_skill_lane(tmp_path):
    search_hint = (
        "web_search needs a search API key. Configure BRAVE_API_KEY, "
        "PERPLEXITY_API_KEY, XAI_API_KEY, or KIMI_API_KEY/MOONSHOT_API_KEY "
        "in tools.web.search or your environment. For direct page fetches, use web_fetch."
    )
    captured_messages: list[list[dict[str, str]]] = []

    async def _call_llm(messages, _models):
        captured_messages.append(messages)
        return LLMResponse(content="handled via skill fallback"), None

    loop = SimpleNamespace(
        max_iterations=2,
        context_guard=SimpleNamespace(check_overflow=lambda _messages, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(side_effect=_call_llm),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _execute_required_tool_fallback=AsyncMock(return_value=search_hint),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(
            get=lambda _name: None,
            execute=AsyncMock(return_value="unused"),
            has=lambda name: name in {"web_search", "web_fetch", "exec"},
        ),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        bus=SimpleNamespace(
            publish_outbound=AsyncMock(return_value=None),
            take_pending_inbound_for_session=lambda *_args, **_kwargs: [],
        ),
        exec_auto_approve=False,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
    )

    msg = InboundMessage(
        channel="cli",
        chat_id="skill-lane",
        sender_id="user",
        content="saham bbca berapa sekarang",
        metadata={
            "required_tool": "web_search",
            "required_tool_query": "saham bbca berapa sekarang",
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
            "turn_category": "action",
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "handled via skill fallback"
    loop._execute_required_tool_fallback.assert_awaited_once_with("web_search", msg)
    assert loop._call_llm_with_fallback.await_count == 1
    assert captured_messages
    continuation_note = "\n".join(
        str(item.get("content") or "")
        for item in captured_messages[0]
        if isinstance(item, dict) and item.get("role") == "user"
    )
    assert "Continue the same user task now instead of stopping on setup." in continuation_note
    assert "Selected skill lane: yahoo-finance-stock." in continuation_note
    assert "Do not call `web_search` again in this turn" in continuation_note


@pytest.mark.asyncio
async def test_run_agent_loop_tool_called_web_search_setup_hint_continues_with_skill_lane(tmp_path):
    search_hint = (
        "web_search needs a search API key. Configure BRAVE_API_KEY, "
        "PERPLEXITY_API_KEY, XAI_API_KEY, or KIMI_API_KEY/MOONSHOT_API_KEY "
        "in tools.web.search or your environment. For direct page fetches, use web_fetch."
    )
    first_response = LLMResponse(
        content="checking",
        tool_calls=[
            ToolCallRequest(
                id="call_search",
                name="web_search",
                arguments={"query": "saham bbca berapa sekarang"},
            )
        ],
    )
    final_response = LLMResponse(content="continued after search setup failure")
    captured_messages: list[list[dict[str, str]]] = []

    async def _call_llm(messages, _models):
        captured_messages.append(messages)
        if len(captured_messages) == 1:
            return first_response, None
        return final_response, None

    execute_mock = AsyncMock(return_value=search_hint)
    loop = SimpleNamespace(
        max_iterations=3,
        context_guard=SimpleNamespace(check_overflow=lambda _messages, _model: False),
        compactor=SimpleNamespace(compact=AsyncMock()),
        _resolve_models_for_message=lambda _msg: ["openai-codex/gpt-5.3-codex"],
        _is_weak_model=lambda _model: False,
        _required_tool_for_query=lambda _q: None,
        _plan_task=AsyncMock(return_value=None),
        _apply_think_mode=lambda m, _s: m,
        _call_llm_with_fallback=AsyncMock(side_effect=_call_llm),
        _self_evaluate=lambda _q, _a: (True, None),
        _critic_evaluate=AsyncMock(return_value=(10, "ok")),
        _log_lesson=AsyncMock(),
        _execute_required_tool_fallback=AsyncMock(return_value=None),
        _should_log_verbose=lambda _session: False,
        _format_verbose_output=lambda _tool, _result, _tokens: "",
        _format_tool_result=lambda result: str(result),
        _get_tool_status_message=lambda _tool, _args: None,
        _get_tool_permissions=lambda _session: {},
        _resolve_agent_id_for_message=lambda _msg: "main",
        context=ContextBuilder(tmp_path),
        memory=SimpleNamespace(add_message=AsyncMock(return_value=None)),
        tools=SimpleNamespace(
            get=lambda _name: None,
            execute=execute_mock,
            has=lambda name: name in {"web_search", "web_fetch", "exec"},
        ),
        loop_detector=SimpleNamespace(
            check=lambda _name, _params: SimpleNamespace(stuck=False, level="ok", message=""),
            record=lambda _name, _params, _call_id: None,
        ),
        truncator=SimpleNamespace(
            truncate=lambda value, _tool_name: value,
            _count_tokens=lambda _value: 0,
        ),
        bus=SimpleNamespace(
            publish_outbound=AsyncMock(return_value=None),
            take_pending_inbound_for_session=lambda *_args, **_kwargs: [],
        ),
        exec_auto_approve=False,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        provider=SimpleNamespace(chat=AsyncMock(return_value=LLMResponse(content="unused"))),
    )

    async def _process_tool_calls(_msg, messages, response, _session):
        return await process_tool_calls(loop, _msg, messages, response, _session)

    loop._process_tool_calls = AsyncMock(side_effect=_process_tool_calls)

    msg = InboundMessage(
        channel="cli",
        chat_id="tool-loop",
        sender_id="user",
        content="saham bbca berapa sekarang",
        metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
            "turn_category": "action",
        },
    )
    session = SimpleNamespace(metadata={})

    result = await run_agent_loop(loop, msg, [{"role": "user", "content": msg.content}], session)

    assert result == "continued after search setup failure"
    assert execute_mock.await_count == 1
    assert loop._call_llm_with_fallback.await_count == 2
    assert len(captured_messages) == 2
    continuation_note = "\n".join(
        str(item.get("content") or "")
        for item in captured_messages[1]
        if isinstance(item, dict) and item.get("role") == "user"
    )
    assert "Continue the same user task now instead of stopping on setup." in continuation_note
    assert "Selected skill lane: yahoo-finance-stock." in continuation_note
