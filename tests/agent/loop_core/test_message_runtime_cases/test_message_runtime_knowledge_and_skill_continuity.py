import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime import process_message
from kabot.bus.events import InboundMessage, OutboundMessage


@pytest.mark.asyncio
@pytest.mark.parametrize("followup_text", ["just explain", "use English", "don't use web search"])
async def test_process_message_web_search_setup_hint_followups_demote_back_to_grounded_answer_mode(
    followup_text: str,
):
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "can you explain about earth? what is earth or something, everything you know about earth",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "web_search",
                "source": "can you explain about earth? what is earth or something, everything you know about earth",
                "updated_at": time.time(),
            },
        }
    )

    history = [
        {
            "role": "assistant",
            "content": (
                "web_search needs a search API key. Configure BRAVE_API_KEY, "
                "PERPLEXITY_API_KEY, XAI_API_KEY, or KIMI_API_KEY/MOONSHOT_API_KEY in "
                "tools.web.search or your environment. For direct page fetches, use web_fetch."
            ),
        }
    ]

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: history),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content=followup_text,
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") is None
    assert "earth" in captured["current_message"].lower()
    assert "web search" in captured["current_message"].lower()
    assert session.metadata.get("pending_followup_tool") is None


@pytest.mark.asyncio
async def test_process_message_language_switch_followup_no_longer_uses_indonesian_web_parser():
    context_builder = MagicMock()
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "harga saham bbca sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "web_search",
                "source": "harga saham bbca sekarang",
                "updated_at": time.time(),
            },
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="simple")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="pakai bahasa inggris",
    )
    await process_message(loop, msg)

    loop._run_simple_response.assert_awaited_once()
    loop._run_agent_loop.assert_not_called()
    assert msg.metadata.get("required_tool") is None
    context_builder.build_messages.assert_not_called()
    assert session.metadata.get("pending_followup_tool") is None


@pytest.mark.asyncio
async def test_process_message_web_search_source_followup_prefers_selected_source_contract():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "yahoo finance"}]
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "harga saham bbca sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "web_search",
                "source": "harga saham bbca sekarang",
                "updated_at": time.time(),
            },
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda name: name in {"web_search", "web_fetch"}),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="yahoo finance",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "web_search"
    required_query = str(msg.metadata.get("required_tool_query") or "").lower()
    assert "bbca" in required_query
    assert "site:finance.yahoo.com" in required_query
    loop._run_agent_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_web_source_followup_rehydrates_active_external_skill_lane_from_session():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = list(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": "yahoo finance"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(
        metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "harga saham bbca sekarang",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "web_search",
                "source": "harga saham bbca sekarang",
                "updated_at": time.time(),
            },
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda name: name in {"web_search", "web_fetch"}),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="yahoo finance",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "web_search"
    assert msg.metadata.get("forced_skill_names") == ["yahoo-finance-stock"]
    assert msg.metadata.get("external_skill_lane") is True
    assert captured["skill_names"] == ["yahoo-finance-stock"]
    assert "[External Skill Continuity Note]" in str(captured["current_message"])
    assert "yahoo-finance-stock" in str(captured["current_message"])
    loop._run_agent_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_same_domain_live_finance_turn_rehydrates_matching_session_skill_lane():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = list(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": "saham bbri berapa"}]

    skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": True,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": True,
        match_skill_details=lambda _message, profile="GENERAL", max_results=3, filter_unavailable=False: [
            {
                "name": "yahoo-finance-stock",
                "source": "workspace",
                "eligible": True,
                "description": "Yahoo Finance stock quote workflow",
            }
        ],
    )
    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = skills
    session = SimpleNamespace(
        metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["web_search", "web_fetch"],
            has=lambda name: name in {"web_search", "web_fetch"},
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="saham bbri berapa",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") is None
    assert msg.metadata.get("forced_skill_names") == ["yahoo-finance-stock"]
    assert msg.metadata.get("external_skill_lane") is True
    assert captured["skill_names"] == ["yahoo-finance-stock"]
    assert "[External Skill Continuity Note]" in str(captured["current_message"])
    loop._run_agent_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_short_active_skill_followup_stays_on_external_skill_lane():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = list(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": captured["current_message"]}]

    skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": True,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": True,
        match_skill_details=lambda _message, profile="GENERAL", max_results=3, filter_unavailable=False: [
            {
                "name": "yahoo-finance-stock",
                "source": "workspace",
                "eligible": True,
                "description": "Yahoo Finance stock quote workflow",
            }
        ],
    )
    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = skills
    session = SimpleNamespace(
        metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["web_fetch", "exec"],
            has=lambda name: name in {"web_fetch", "exec"},
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="skills saham nya dipake",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("forced_skill_names") == ["yahoo-finance-stock"]
    assert msg.metadata.get("external_skill_lane") is True
    assert msg.metadata.get("requires_real_skill_execution") is True
    assert captured["skill_names"] == ["yahoo-finance-stock"]
    assert "[External Skill Continuity Note]" in str(captured["current_message"])
    loop._run_agent_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_unrelated_explicit_new_request_clears_persisted_external_skill_lane():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "latest news about earth today"}]
    context_builder.skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": False,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
        match_skill_details=lambda _message, profile="GENERAL", max_results=3, filter_unavailable=False: [],
    )
    session = SimpleNamespace(
        metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="RESEARCH", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["web_search"],
            has=lambda name: name == "web_search",
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="latest news about earth today",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("external_skill_lane") is False
    assert msg.metadata.get("forced_skill_names") is None
    assert session.metadata.get("external_skill_lane") is False
    assert session.metadata.get("forced_skill_names") is None
    assert msg.metadata.get("required_tool") == "web_search"
    loop._run_agent_loop.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_live_finance_lookup_prefers_web_search_in_general_route():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "saham bbca berapa"}]
    context_builder.skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": False,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
    )
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["web_search", "web_fetch"],
            has=lambda name: name in {"web_search", "web_fetch"},
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="saham bbca berapa",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "web_search"
    assert str(msg.metadata.get("required_tool_query") or "").lower() == "saham bbca berapa"
    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_live_finance_lookup_falls_back_to_stock_tool_without_web_search():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "saham bbca berapa"}]
    context_builder.skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": False,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
    )
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["stock"],
            has=lambda name: name == "stock",
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="saham bbca berapa",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "stock"
    assert str(msg.metadata.get("required_tool_query") or "").lower() == "saham bbca berapa"
    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_live_finance_lookup_without_live_tools_adds_honesty_note():
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": False,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
    )
    session = SimpleNamespace(metadata={})

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="saham bbca berapa",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") is None
    assert "do not guess a latest price" in captured["current_message"].lower()
    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_live_data_refresh_followup_keeps_grounded_web_search_lookup():
    context_builder = MagicMock()
    context_builder.build_messages.return_value = [{"role": "user", "content": "pakai data terbaru"}]
    context_builder.skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": False,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
    )
    session = SimpleNamespace(
        metadata={
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "saham bbca berapa",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "web_search",
                "source": "saham bbca berapa",
                "updated_at": time.time(),
            },
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["web_search", "web_fetch"],
            has=lambda name: name in {"web_search", "web_fetch"},
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="pakai data terbaru",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "web_search"
    required_query = str(msg.metadata.get("required_tool_query") or "").lower()
    assert "bbca" in required_query
    assert "terbaru" in required_query
    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_live_data_refresh_followup_without_live_tools_keeps_honesty_context():
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": False,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
    )
    session = SimpleNamespace(
        metadata={
            "pending_followup_intent": {
                "text": "saham bbca berapa",
                "profile": "GENERAL",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
                "request_text": "saham bbca berapa",
            },
            "last_tool_context": {
                "tool": "message",
                "source": "saham bbca berapa",
                "updated_at": time.time(),
            },
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="pakai data terbaru",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") is None
    assert "saham bbca berapa" in captured["current_message"].lower()
    assert "do not guess a latest price" in captured["current_message"].lower()
    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_live_data_refresh_followup_rehydrates_active_finance_skill_lane():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = list(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": "pakai data terbaru"}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = SimpleNamespace(
        should_prefer_external_finance_skill=lambda _text, profile="GENERAL": False,
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
    )
    session = SimpleNamespace(
        metadata={
            "external_skill_lane": True,
            "forced_skill_names": ["yahoo-finance-stock"],
            "pending_followup_tool": {
                "tool": "web_search",
                "source": "saham bbca berapa",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            },
            "last_tool_context": {
                "tool": "web_search",
                "source": "saham bbca berapa",
                "updated_at": time.time(),
            },
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=SimpleNamespace(fast_first_response=True),
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(
            tool_names=["web_search", "web_fetch"],
            has=lambda name: name in {"web_search", "web_fetch"},
        ),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="pakai data terbaru",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("required_tool") == "web_search"
    assert msg.metadata.get("forced_skill_names") == ["yahoo-finance-stock"]
    assert msg.metadata.get("external_skill_lane") is True
    required_query = str(msg.metadata.get("required_tool_query") or "").lower()
    assert "bbca" in required_query
    assert "terbaru" in required_query
    assert captured["skill_names"] == ["yahoo-finance-stock"]
    assert "[External Skill Continuity Note]" in str(captured["current_message"])
    loop._run_agent_loop.assert_awaited_once()
    loop._run_simple_response.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "followup_text",
    ["struktur skillsnya gimana", "flow skillnya gimana", "template skillnya dong"],
)
async def test_process_message_skill_structure_followups_keep_skill_creator_lane(
    followup_text: str,
):
    captured: dict[str, str] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = ",".join(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(
        metadata={
            "skill_creation_flow": {
                "request_text": "buat skill baru untuk EV monitor",
                "stage": "discovery",
                "updated_at": time.time(),
                "expires_at": time.time() + 300,
            }
        }
    )

    loop = SimpleNamespace(
        _active_turn_id=None,
        runtime_performance=None,
        _parse_approval_command=lambda _content: None,
        command_router=SimpleNamespace(is_command=lambda _content: False),
        _init_session=AsyncMock(return_value=session),
        _cold_start_reported=True,
        directive_parser=SimpleNamespace(
            parse=lambda content: (
                content,
                SimpleNamespace(
                    raw_directives=[],
                    think=False,
                    verbose=False,
                    elevated=False,
                    model=None,
                ),
            )
        ),
        memory=SimpleNamespace(get_conversation_context=lambda _key, max_messages=30: []),
        router=SimpleNamespace(
            route=AsyncMock(return_value=SimpleNamespace(profile="CHAT", is_complex=False))
        ),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=SimpleNamespace(tool_names=[]),
        _required_tool_for_query=lambda _text: None,
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content=followup_text,
    )
    await process_message(loop, msg)

    assert "skill-creator" in captured["skill_names"]
    assert "[Skill Workflow]" in captured["current_message"]
    assert "buat skill baru untuk EV monitor" in captured["current_message"]
    assert msg.metadata.get("skill_creation_guard", {}).get("active") is True
