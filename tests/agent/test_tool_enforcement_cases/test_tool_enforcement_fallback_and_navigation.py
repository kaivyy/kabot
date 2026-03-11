"""Split from tests/agent/test_tool_enforcement.py to keep test modules below 1000 lines.
Chunk 2: test_execute_required_tool_fallback_stock_uses_name_resolution_when_ticker_not_explicit .. test_agent_loop_process_direct_keeps_multilingual_location_queries_ai_driven.
"""

import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.loop import AgentLoop
from kabot.agent.loop_core import tool_enforcement as tool_enforcement_module
from kabot.bus.events import InboundMessage
from kabot.bus.queue import MessageBus
from kabot.cron.service import CronService
from kabot.providers.base import LLMResponse, ToolCallRequest
from kabot.session.manager import Session


class _InMemorySessionManager:
    def __init__(self):
        self._cache: dict[str, Session] = {}

    def get_or_create(self, key: str) -> Session:
        if key not in self._cache:
            self._cache[key] = Session(key=key)
        return self._cache[key]

    def save(self, session: Session) -> None:
        self._cache[session.key] = session


class _RecordingLLMProvider:
    def __init__(self):
        self.calls: list[str] = []

    def get_default_model(self) -> str:
        return "openai-codex/gpt-5.3-codex"

    async def chat(
        self,
        messages,
        tools=None,
        model=None,
        max_tokens=4096,
        temperature=0.7,
    ):
        user_message = next(
            (str(item.get("content") or "") for item in reversed(messages) if item.get("role") == "user"),
            "",
        )
        self.calls.append(user_message)

        workspace_match = re.search(r"Current workspace path: (.+)", user_message)
        last_path_match = re.search(r"Last navigated filesystem path: (.+)", user_message)
        workspace_path = workspace_match.group(1).strip() if workspace_match else ""
        last_path = last_path_match.group(1).strip() if last_path_match else ""

        if "你现在在哪个" in user_message:
            content = f"我现在在工作区 {workspace_path}，最近查看的文件夹是 {last_path}。"
        elif "ตอนนี้คุณอยู่" in user_message:
            content = f"ตอนนี้ฉันอยู่ที่ workspace {workspace_path} และโฟลเดอร์ล่าสุดคือ {last_path}"
        else:
            content = f"Current workspace: {workspace_path}; last path: {last_path}"

        return LLMResponse(content=content)


@pytest.fixture
def agent_loop(tmp_path):
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
    return AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron_jobs.json"),
    )

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_uses_name_resolution_when_ticker_not_explicit(agent_loop):
    execute_mock = AsyncMock(return_value="[STOCK] 7203.T (TSE)\nPrice: 1.00 JPY")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="toyota sekarang berapa",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert "7203.T" in result
    execute_mock.assert_awaited_once_with("stock", {"symbol": "toyota sekarang berapa"})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_keeps_ticker_hint_when_name_resolution_fails(agent_loop):
    execute_mock = AsyncMock(
        return_value=i18n_t("stock.need_symbol", "umur kamu berapa sekarang")
    )
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="umur kamu berapa sekarang",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert "ticker" in result.lower()
    execute_mock.assert_not_awaited()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_crypto_supports_multi_coin_mentions(agent_loop):
    execute_mock = AsyncMock(return_value="crypto-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="kalau harga bitcoin dan ethereum berapa sekarang",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("crypto", msg)
    assert result == "crypto-ok"
    execute_mock.assert_awaited_once_with("crypto", {"coin": "bitcoin,ethereum"})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_crypto_short_followup_with_new_coin_prefers_raw_text(agent_loop):
    execute_mock = AsyncMock(return_value="crypto-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="ethereum berapa",
        metadata={"required_tool_query": "kalau harga bitcoin dan ethereum berapa sekarang"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("crypto", msg)
    assert result == "crypto-ok"
    execute_mock.assert_awaited_once_with("crypto", {"coin": "ethereum"})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_without_ticker_routes_to_web_search(agent_loop):
    execute_mock = AsyncMock(return_value="search-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="harga top saham indonesia sekarang",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "search-ok"
    execute_mock.assert_awaited_once_with(
        "web_search",
        {
            "query": "harga top saham indonesia sekarang",
            "count": 5,
            "context_text": "harga top saham indonesia sekarang",
        },
    )


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_uses_jkse_alias_without_prompting_symbol(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="cek harga ihsg realtime pakai simbol jkse",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "^JKSE"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_ignores_verbose_stale_metadata_on_short_confirmation(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="iya",
        metadata={
            "required_tool_query": (
                "Iya, kamu bener. Aku kebablasan mode ticker dari teks bebas. "
                "BBRI.JK BBCA.JK BMRI.JK XXXX.JK"
            )
        },
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert "ticker" in result.lower()
    execute_mock.assert_not_awaited()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_ignores_verbose_stale_metadata_on_low_information_followup(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="iya kamu bener lanjut",
        metadata={
            "required_tool_query": (
                "Iya, kamu bener. Aku kebablasan mode ticker dari teks bebas. "
                "BBRI.JK BBCA.JK BMRI.JK"
            )
        },
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert "ticker" in result.lower()
    execute_mock.assert_not_awaited()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_does_not_parse_plain_confirmation_words(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="iya kamu bener maaf itu dari aku",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert "ticker" in result.lower()
    execute_mock.assert_not_awaited()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_keeps_only_valid_symbols_from_mixed_text(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="iya, kamu bener. kalau saham bbri bbca bmri berapa sekarang tanpa spam error per kata",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "BBRI.JK,BBCA.JK,BMRI.JK"})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_calls_cron_tool(agent_loop):
    execute_mock = AsyncMock(return_value="Created job 'makan' (id: abc123)")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ingatkan 2 menit lagi makan",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "Created job" in result

    assert execute_mock.await_count == 1
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "cron"
    assert params["action"] == "add"
    assert params["one_shot"] is True
    assert isinstance(params["at_time"], str)
    assert "makan" in params["message"].lower()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_can_list_groups(agent_loop):
    execute_mock = AsyncMock(return_value="Schedule groups:\n- Shift A (group_id: grp_shift_a, jobs: 2)")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="tolong list jadwal reminder saya",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "Schedule groups" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "cron"
    assert params["action"] == "list_groups"
    assert params["context_text"] == msg.content

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_can_remove_group_by_id(agent_loop):
    execute_mock = AsyncMock(return_value="Removed group 'Shift A' (grp_shift_a) with 4 jobs")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="hapus jadwal group grp_shift_a",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "Removed group" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "cron"
    assert params["action"] == "remove_group"
    assert params["group_id"] == "grp_shift_a"
    assert params["context_text"] == msg.content

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_remove_needs_selector_in_english(agent_loop):
    execute_mock = AsyncMock(return_value="should not run")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="please remove my reminder schedule",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "provide `group_id`" in result.lower()
    assert "jadwal" not in result.lower()
    execute_mock.assert_not_awaited()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_remove_needs_selector_in_indonesian(agent_loop):
    execute_mock = AsyncMock(return_value="should not run")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="tolong hapus jadwal reminder saya",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "sebutkan `group_id`" in result.lower()
    execute_mock.assert_not_awaited()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_can_update_group_schedule(agent_loop):
    execute_mock = AsyncMock(return_value="Updated group 'Shift A' (grp_shift_a) with 6 jobs")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ubah jadwal grp_shift_a tiap 12 jam",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "Updated group" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "cron"
    assert params["action"] == "update_group"
    assert params["group_id"] == "grp_shift_a"
    assert params["every_seconds"] == 12 * 3600
    assert params["one_shot"] is False
    assert params["context_text"] == msg.content

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_can_rename_group(agent_loop):
    execute_mock = AsyncMock(return_value="Updated group 'Shift Team A Baru' (grp_shift_a) with 6 jobs")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ubah judul grp_shift_a jadi Shift Team A Baru",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "Updated group" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "cron"
    assert params["action"] == "update_group"
    assert params["group_id"] == "grp_shift_a"
    assert params["new_title"] == "Shift Team A Baru"
    assert params["context_text"] == msg.content

@pytest.mark.asyncio
async def test_run_agent_loop_does_not_schedule_duplicate_after_required_tool_called(agent_loop):
    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ingatkan 2 menit lagi makan",
        timestamp=datetime.now(),
    )
    messages = [{"role": "user", "content": msg.content}]
    session = MagicMock()
    session.metadata = {}

    agent_loop._plan_task = AsyncMock(return_value=None)
    agent_loop._apply_think_mode = MagicMock(side_effect=lambda m, s: m)
    agent_loop._self_evaluate = MagicMock(return_value=(True, None))
    agent_loop._critic_evaluate = AsyncMock(return_value=(8, "ok"))
    agent_loop._log_lesson = AsyncMock(return_value=None)

    first = LLMResponse(
        content="",
        tool_calls=[
            ToolCallRequest(
                id="call_1",
                name="cron",
                arguments={
                    "action": "add",
                    "message": "makan",
                    "at_time": "2026-02-20T09:12:00+07:00",
                    "one_shot": True,
                },
            )
        ],
    )
    second = LLMResponse(content="Created job 'makan' (id: abc123)", tool_calls=[])
    agent_loop._call_llm_with_fallback = AsyncMock(side_effect=[(first, None), (second, None)])

    execute_mock = AsyncMock(return_value="Created job 'makan' (id: abc123)")
    agent_loop.tools.execute = execute_mock

    result = await agent_loop._run_agent_loop(msg, messages, session)
    assert "Created job" in str(result)
    assert execute_mock.await_count == 1
    assert agent_loop._critic_evaluate.await_count == 0

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_supports_recurring_interval(agent_loop):
    execute_mock = AsyncMock(return_value="Created recurring job 'minum air' (id: abc123)")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ingatkan tiap 4 jam minum air",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "Created" in result

    assert execute_mock.await_count == 1
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "cron"
    assert params["action"] == "add"
    assert params["every_seconds"] == 4 * 3600
    assert params["one_shot"] is False
    assert "minum air" in params["message"].lower()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_supports_daily_time(agent_loop):
    execute_mock = AsyncMock(return_value="Created daily job 'standup tim' (id: abc123)")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ingatkan setiap hari jam 09:30 standup tim",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "Created" in result

    assert execute_mock.await_count == 1
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "cron"
    assert params["action"] == "add"
    assert params["cron_expr"] == "30 9 * * *"
    assert params["one_shot"] is False
    assert "standup tim" in params["message"].lower()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_supports_shift_cycle_pattern(agent_loop):
    execute_mock = AsyncMock(return_value="Created recurring shift reminder")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content=(
            "ingatkan hari ini masuk malam jam 00:00-08:00 selama 3 hari, setelah itu libur 1 hari, "
            "masuk sore jam 16:00-00:00 selama 3 hari, setelah itu libur 1 hari, "
            "masuk pagi jam 08:00-16:00 selama 3 hari, setelah itu libur 1 hari, berulang terus"
        ),
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "group_id" in result

    # 9 work-days, each with start+end reminders -> 18 recurring jobs in a 12-day cycle.
    assert execute_mock.await_count == 18
    for call in execute_mock.await_args_list:
        tool_name, params = call.args
        assert tool_name == "cron"
        assert params["action"] == "add"
        assert params["every_seconds"] == 12 * 86400
        assert params["one_shot"] is False
        assert isinstance(params["start_at"], str)

    all_messages = [call.args[1]["message"].lower() for call in execute_mock.await_args_list]
    assert any("malam" in m for m in all_messages)
    assert any("sore" in m for m in all_messages)
    assert any("pagi" in m for m in all_messages)

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_supports_generic_cycle_pattern(agent_loop):
    execute_mock = AsyncMock(return_value="Created recurring cycle reminder")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content=(
            "ingatkan fokus coding jam 09:00 selama 5 hari, libur 2 hari, "
            "review sprint jam 14:00 selama 1 hari, libur 1 hari, berulang"
        ),
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "group_id" in result

    # 6 work-days total with one daily reminder each.
    assert execute_mock.await_count == 6
    for call in execute_mock.await_args_list:
        tool_name, params = call.args
        assert tool_name == "cron"
        assert params["action"] == "add"
        assert params["every_seconds"] == 9 * 86400
        assert params["one_shot"] is False
        assert isinstance(params["start_at"], str)

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_cron_supports_custom_3_1_2_1_cycle(agent_loop):
    execute_mock = AsyncMock(return_value="Created recurring cycle reminder")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content=(
            "ingatkan masuk pagi jam 08:00 selama 3 hari, libur 1 hari, "
            "masuk sore jam 16:00 selama 2 hari, libur 1 hari, berulang terus"
        ),
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("cron", msg)
    assert "group_id" in result

    # (3 + 2) work-days with one reminder each, repeating every 7 days.
    assert execute_mock.await_count == 5
    group_ids = set()
    titles = set()
    for call in execute_mock.await_args_list:
        tool_name, params = call.args
        assert tool_name == "cron"
        assert params["action"] == "add"
        assert params["every_seconds"] == 7 * 86400
        assert params["one_shot"] is False
        assert isinstance(params["start_at"], str)
        assert isinstance(params["title"], str) and params["title"]
        assert isinstance(params["group_id"], str) and params["group_id"]
        group_ids.add(params["group_id"])
        titles.add(params["title"])

    assert len(group_ids) == 1
    assert len(titles) == 1

@pytest.mark.asyncio
async def test_agent_loop_process_direct_supports_multilingual_directory_navigation_smoke(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_desktop = fake_home / "Desktop"
    fake_bot = fake_desktop / "bot"
    fake_bot.mkdir(parents=True)
    (fake_desktop / "note.txt").write_text("hello", encoding="utf-8")
    (fake_bot / "CHANGELOG.md").write_text("demo", encoding="utf-8")

    provider = _RecordingLLMProvider()
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path / "workspace",
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron_jobs.json"),
        session_manager=_InMemorySessionManager(),
    )
    loop.workspace.mkdir(parents=True, exist_ok=True)
    loop.memory = SimpleNamespace(
        create_session=lambda *args, **kwargs: None,
        add_message=AsyncMock(return_value=None),
        get_conversation_context=lambda *args, **kwargs: [],
        metadata=SimpleNamespace(add_lesson=lambda **kwargs: None),
    )
    loop.sentinel = SimpleNamespace(mark_session_active=lambda **kwargs: None)
    loop._ensure_memory_warmup_task = lambda: None
    loop.router = SimpleNamespace(route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False)))
    loop.context.build_messages = MagicMock(
        side_effect=lambda history, current_message, **kwargs: [
            {"role": "system", "content": "ctx"},
            {"role": "user", "content": current_message},
        ]
    )
    loop._resolve_context_for_message = lambda _msg: loop.context
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: Path(fake_home))

    first = await loop.process_direct("显示桌面文件夹内容", session_key="cli:fs-smoke", chat_id="fs-smoke")
    second = await loop.process_direct("表示 フォルダ bot", session_key="cli:fs-smoke", chat_id="fs-smoke")
    thai_first = await loop.process_direct("เปิดโฟลเดอร์เดสก์ท็อป", session_key="cli:fs-smoke-th", chat_id="fs-smoke-th")
    third = await loop.process_direct("เปิด โฟลเดอร์ bot", session_key="cli:fs-smoke-th", chat_id="fs-smoke-th")

    assert "bot" in first
    assert "note.txt" in first
    assert "CHANGELOG.md" in second
    assert "bot" in thai_first
    assert "CHANGELOG.md" in third
    assert provider.calls == []

@pytest.mark.asyncio
async def test_agent_loop_process_direct_keeps_multilingual_location_queries_ai_driven(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_desktop = fake_home / "Desktop"
    fake_bot = fake_desktop / "bot"
    fake_bot.mkdir(parents=True)
    (fake_bot / "CHANGELOG.md").write_text("demo", encoding="utf-8")

    provider = _RecordingLLMProvider()
    workspace = tmp_path / "workspace"
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=workspace,
        model="openai-codex/gpt-5.3-codex",
        cron_service=CronService(tmp_path / "cron_jobs.json"),
        session_manager=_InMemorySessionManager(),
    )
    workspace.mkdir(parents=True, exist_ok=True)
    loop.memory = SimpleNamespace(
        create_session=lambda *args, **kwargs: None,
        add_message=AsyncMock(return_value=None),
        get_conversation_context=lambda *args, **kwargs: [],
        metadata=SimpleNamespace(add_lesson=lambda **kwargs: None),
    )
    loop.sentinel = SimpleNamespace(mark_session_active=lambda **kwargs: None)
    loop._ensure_memory_warmup_task = lambda: None
    loop.router = SimpleNamespace(route=AsyncMock(return_value=SimpleNamespace(profile="GENERAL", is_complex=False)))
    loop.context.build_messages = MagicMock(
        side_effect=lambda history, current_message, **kwargs: [
            {"role": "system", "content": "ctx"},
            {"role": "user", "content": current_message},
        ]
    )
    loop._resolve_context_for_message = lambda _msg: loop.context
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: Path(fake_home))

    await loop.process_direct("显示桌面文件夹内容", session_key="cli:fs-location", chat_id="fs-location")
    await loop.process_direct("表示 フォルダ bot", session_key="cli:fs-location", chat_id="fs-location")

    chinese = await loop.process_direct("你现在在哪个文件夹", session_key="cli:fs-location", chat_id="fs-location")
    thai = await loop.process_direct("ตอนนี้คุณอยู่โฟลเดอร์ไหน", session_key="cli:fs-location", chat_id="fs-location")

    expected_workspace = str(workspace.resolve())
    expected_last_path = str(fake_bot.resolve())
    assert expected_workspace in chinese
    assert expected_last_path in chinese
    assert expected_workspace in thai
    assert expected_last_path in thai
    location_calls = [call for call in provider.calls if "[System Note: Filesystem location context]" in call]
    assert len(location_calls) == 2
