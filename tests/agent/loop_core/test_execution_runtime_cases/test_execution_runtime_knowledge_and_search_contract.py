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


def test_live_research_latch_yields_to_external_skill_match():
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


def test_live_research_latch_stays_enabled_without_external_skill_match():
    loop = SimpleNamespace(
        context=SimpleNamespace(
            skills=SimpleNamespace(
                has_preferred_external_skill_match=lambda text, profile="GENERAL": False
            )
        )
    )

    assert not _should_defer_live_research_latch_to_skill(
        loop,
        "latest news about earth today",
        profile="RESEARCH",
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
