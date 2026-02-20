from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.loop import AgentLoop
from kabot.bus.events import InboundMessage
from kabot.bus.queue import MessageBus
from kabot.cron.service import CronService
from kabot.providers.base import LLMResponse, ToolCallRequest


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


def test_required_tool_for_query_detects_weather_and_reminder(agent_loop):
    assert agent_loop._required_tool_for_query("tolong cek suhu cilacap hari ini") == "weather"
    assert agent_loop._required_tool_for_query("ingatkan 2 menit lagi makan") == "cron"
    assert agent_loop._required_tool_for_query("tolong list jadwal reminder saya") == "cron"
    assert agent_loop._required_tool_for_query("hai") is None


def test_required_tool_for_query_detects_multilingual_weather_and_reminder(agent_loop):
    assert agent_loop._required_tool_for_query("เตือนฉันอีก 2 นาทีให้กินข้าว") == "cron"
    assert agent_loop._required_tool_for_query("อากาศกรุงเทพวันนี้") == "weather"
    assert agent_loop._required_tool_for_query("两分钟后提醒我吃饭") == "cron"
    assert agent_loop._required_tool_for_query("北京今天天气怎么样") == "weather"


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_weather_calls_weather_tool(agent_loop):
    execute_mock = AsyncMock(return_value="Cilacap: 27C, cerah")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="cek suhu Cilacap hari ini",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("weather", msg)
    assert result == "Cilacap: 27C, cerah"
    execute_mock.assert_awaited_once_with(
        "weather",
        {"location": "Cilacap", "context_text": "cek suhu Cilacap hari ini"},
    )


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
