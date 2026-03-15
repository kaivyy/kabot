from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop_core.message_runtime import process_message
from kabot.bus.events import InboundMessage, OutboundMessage


def _make_loop(
    *,
    session: SimpleNamespace,
    context_builder: MagicMock,
    route_decisions: list[SimpleNamespace],
    tools: SimpleNamespace | None = None,
    required_tool_for_query=None,
):
    return SimpleNamespace(
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
        router=SimpleNamespace(route=AsyncMock(side_effect=route_decisions)),
        _resolve_context_for_message=lambda _msg: context_builder,
        context=context_builder,
        tools=tools or SimpleNamespace(tool_names=[], has=lambda _name: False),
        _required_tool_for_query=required_tool_for_query or (lambda _text: None),
        _run_simple_response=AsyncMock(return_value="simple"),
        _run_agent_loop=AsyncMock(return_value="agent"),
        _finalize_session=AsyncMock(
            return_value=OutboundMessage(channel="telegram", chat_id="chat-1", content="agent")
        ),
        sessions=SimpleNamespace(save=lambda _session: None),
        runtime_observability=None,
    )


@pytest.mark.asyncio
async def test_transcript_finance_skill_followup_stays_on_external_lane():
    captured: list[dict[str, object]] = []

    def _build_messages(**kwargs):
        captured.append(
            {
                "current_message": str(kwargs.get("current_message") or ""),
                "skill_names": list(kwargs.get("skill_names") or []),
            }
        )
        return [{"role": "user", "content": str(kwargs.get("current_message") or "")}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = SimpleNamespace(
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": True,
        match_skill_details=lambda text, profile="GENERAL", max_results=3, filter_unavailable=False: [
            {
                "name": "yahoo-finance-stock",
                "source": "workspace",
                "eligible": True,
                "description": "Yahoo Finance workflow for stock lookup and quote fetch",
            }
        ],
        match_skills=lambda text, profile="GENERAL", max_results=3: ["yahoo-finance-stock"],
    )
    session = SimpleNamespace(metadata={})
    route_decision = SimpleNamespace(
        profile="GENERAL",
        is_complex=False,
        turn_category="action",
        grounding_mode="web_live_data",
    )
    loop = _make_loop(
        session=session,
        context_builder=context_builder,
        route_decisions=[route_decision, route_decision],
        tools=SimpleNamespace(
            tool_names=["web_search", "web_fetch"],
            has=lambda name: name in {"web_search", "web_fetch"},
        ),
    )

    first = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="saham bbca berapa",
    )
    await process_message(loop, first)

    second = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="pakai data terbaru",
    )
    await process_message(loop, second)

    assert first.metadata.get("forced_skill_names") == ["yahoo-finance-stock"]
    assert session.metadata.get("external_skill_lane") is True
    assert first.metadata.get("requires_real_skill_execution") is True
    assert second.metadata.get("forced_skill_names") == ["yahoo-finance-stock"]
    assert second.metadata.get("external_skill_lane") is True
    assert second.metadata.get("requires_real_skill_execution") is True
    assert captured[0]["skill_names"] == ["yahoo-finance-stock"]
    assert captured[-1]["skill_names"] == ["yahoo-finance-stock"]
    assert "yahoo-finance-stock" in str(captured[-1]["current_message"])
    loop._run_agent_loop.assert_awaited()


@pytest.mark.asyncio
async def test_transcript_crypto_live_query_prefers_external_skill_setup_lane_when_missing():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = list(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = SimpleNamespace(
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": False,
        match_skill_details=lambda text, profile="GENERAL", max_results=3, filter_unavailable=False: [
            {
                "name": "binance-pro",
                "source": "workspace",
                "eligible": False,
                "description": "Binance crypto workflow for balances, quotes, and market checks",
                "install": [{"label": "CLI: jq", "cmd": "brew install jq"}],
                "missing": {"bins": ["jq"], "env": []},
            }
        ],
        _format_skill_unavailability=lambda _detail: "CLI: jq",
    )
    session = SimpleNamespace(metadata={})
    loop = _make_loop(
        session=session,
        context_builder=context_builder,
        route_decisions=[
            SimpleNamespace(
                profile="GENERAL",
                is_complex=False,
                turn_category="action",
                grounding_mode="web_live_data",
            )
        ],
        tools=SimpleNamespace(tool_names=["web_fetch"], has=lambda name: name == "web_fetch"),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="kalau btc di binance sekarang berapa",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("forced_skill_names") == ["binance-pro"]
    assert msg.metadata.get("external_skill_lane") is True
    assert captured["skill_names"] == ["binance-pro"]
    assert "[External Skill Setup Note]" in str(captured["current_message"])
    assert "CLI: jq" in str(captured["current_message"])


@pytest.mark.asyncio
async def test_transcript_custom_api_skill_auto_adapts_without_explicit_skill_phrase():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = list(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = SimpleNamespace(
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": True,
        match_skill_details=lambda text, profile="GENERAL", max_results=3, filter_unavailable=False: [
            {
                "name": "mlbb-id-check",
                "source": "managed",
                "eligible": True,
                "description": "Check Mobile Legends account IDs against an API endpoint",
            }
        ],
        match_skills=lambda text, profile="GENERAL", max_results=3: ["mlbb-id-check"],
    )
    session = SimpleNamespace(metadata={})
    loop = _make_loop(
        session=session,
        context_builder=context_builder,
        route_decisions=[
            SimpleNamespace(
                profile="GENERAL",
                is_complex=False,
                turn_category="action",
                grounding_mode="web_live_data",
            )
        ],
        tools=SimpleNamespace(
            tool_names=["web_fetch", "exec"],
            has=lambda name: name in {"web_fetch", "exec"},
        ),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="cek id game mlbb ini",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("forced_skill_names") == ["mlbb-id-check"]
    assert msg.metadata.get("external_skill_lane") is True
    assert captured["skill_names"] == ["mlbb-id-check"]
    assert "[Skill Adaptation Note]" in str(captured["current_message"])
    assert "mlbb-id-check" in str(captured["current_message"])


@pytest.mark.asyncio
async def test_transcript_direct_github_skill_install_then_approval_stays_in_skill_installer_lane():
    captured: list[dict[str, object]] = []

    def _build_messages(**kwargs):
        captured.append(
            {
                "current_message": str(kwargs.get("current_message") or ""),
                "skill_names": list(kwargs.get("skill_names") or []),
            }
        )
        return [{"role": "user", "content": str(kwargs.get("current_message") or "")}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(metadata={})
    loop = _make_loop(
        session=session,
        context_builder=context_builder,
        route_decisions=[
            SimpleNamespace(profile="GENERAL", is_complex=False),
            SimpleNamespace(profile="CHAT", is_complex=False),
        ],
    )

    first = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="tolong pasang https://github.com/acme/custom-skills/tree/main/skills/mlbb-id-check",
    )
    await process_message(loop, first)
    session.metadata.setdefault("skill_creation_flow", {})["stage"] = "planning"

    second = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="oke lanjut",
    )
    await process_message(loop, second)

    assert "skill-installer" in list(captured[0]["skill_names"])
    assert "[Skill Workflow]" in str(captured[0]["current_message"])
    assert "installing or updating an external Kabot skill" in str(captured[0]["current_message"])
    assert "skill-installer" in list(captured[-1]["skill_names"])
    assert "explicitly approved the plan" in str(captured[-1]["current_message"])
    assert session.metadata.get("skill_creation_flow", {}).get("kind") == "install"
    assert session.metadata.get("skill_creation_flow", {}).get("stage") == "approved"
    assert second.metadata.get("requires_real_skill_execution") is True


@pytest.mark.asyncio
async def test_transcript_recent_created_stock_skill_immediately_loads_existing_skill_for_first_use():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        captured["skill_names"] = list(kwargs.get("skill_names") or [])
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    context_builder.skills = SimpleNamespace(
        has_preferred_external_skill_match=lambda _text, profile="GENERAL": True,
        match_skill_details=lambda text, profile="GENERAL", max_results=3, filter_unavailable=False: [
            {
                "name": "yahoo-finance-stock",
                "source": "workspace",
                "eligible": True,
                "description": "Yahoo Finance workflow for stock lookup and quote fetch",
            }
        ],
        match_skills=lambda text, profile="GENERAL", max_results=3: ["yahoo-finance-stock"],
    )
    session = SimpleNamespace(
        metadata={
            "skill_creation_flow": {
                "request_text": "buat skill untuk cek saham via Yahoo Finance",
                "stage": "approved",
                "kind": "create",
                "updated_at": 1.0,
                "expires_at": 4102444800.0,
            }
        }
    )
    loop = _make_loop(
        session=session,
        context_builder=context_builder,
        route_decisions=[
            SimpleNamespace(
                profile="GENERAL",
                is_complex=False,
                turn_category="action",
                grounding_mode="web_live_data",
            )
        ],
        tools=SimpleNamespace(
            tool_names=["web_fetch", "exec"],
            has=lambda name: name in {"web_fetch", "exec"},
        ),
    )
    loop.memory = SimpleNamespace(
        get_conversation_context=lambda _key, max_messages=30: [
            {
                "role": "assistant",
                "content": "/tmp/workspace/skills/yahoo-finance-stock/SKILL.md",
            }
        ]
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="cek saham goto",
    )
    await process_message(loop, msg)

    assert msg.metadata.get("forced_skill_names") == ["yahoo-finance-stock"]
    assert msg.metadata.get("external_skill_lane") is True
    assert msg.metadata.get("requires_real_skill_execution") is True
    assert captured["skill_names"] == ["yahoo-finance-stock"]
    assert "[Existing Skill Note]" in str(captured["current_message"])
    assert "Do not restart the skill-creator workflow." in str(captured["current_message"])
    assert session.metadata.get("skill_creation_flow") is None


@pytest.mark.asyncio
async def test_transcript_openclaw_repo_inspection_stays_grounded_to_filesystem():
    captured: dict[str, object] = {}

    def _build_messages(**kwargs):
        captured["current_message"] = str(kwargs.get("current_message") or "")
        return [{"role": "user", "content": captured["current_message"]}]

    context_builder = MagicMock()
    context_builder.build_messages.side_effect = _build_messages
    session = SimpleNamespace(
        metadata={
            "working_directory": r"C:\Users\Arvy Kairi\Desktop\bot\openclaw",
            "delivery_route": {"channel": "telegram", "chat_id": "chat-1"},
        }
    )
    loop = _make_loop(
        session=session,
        context_builder=context_builder,
        route_decisions=[
            SimpleNamespace(
                profile="GENERAL",
                is_complex=True,
                turn_category="action",
                grounding_mode="filesystem_inspection",
            )
        ],
        tools=SimpleNamespace(
            tool_names=["list_dir", "read_file", "find_files", "exec"],
            has=lambda name: name in {"list_dir", "read_file", "find_files", "exec"},
        ),
    )

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="chat-1",
        content="periksa seluruh file, aplikasi apa yang ada di folder openclaw, jelaskan dengan detail",
    )
    await process_message(loop, msg)

    assert "[System Note: Grounded filesystem inspection]" in str(captured["current_message"])
    assert r"C:\Users\Arvy Kairi\Desktop\bot\openclaw" in str(captured["current_message"])
    assert "Start with list_dir, read_file, find_files, or exec" in str(captured["current_message"])
    assert msg.metadata.get("requires_grounded_filesystem_inspection") is True
    assert msg.metadata.get("route_grounding_mode") == "filesystem_inspection"
