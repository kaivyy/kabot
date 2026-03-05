from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
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
    assert agent_loop._required_tool_for_query("purwokerto berapa derajat sekarang") == "weather"
    assert agent_loop._required_tool_for_query("ingatkan 2 menit lagi makan") == "cron"
    assert agent_loop._required_tool_for_query("tolong list jadwal reminder saya") == "cron"
    assert agent_loop._required_tool_for_query("cek update kabot sekarang") == "check_update"
    assert agent_loop._required_tool_for_query("update kabot sekarang") == "system_update"
    assert agent_loop._required_tool_for_query("kapasitas ram berapa") == "get_system_info"
    assert agent_loop._required_tool_for_query("cek ram proses sekarang") == "get_process_memory"
    assert agent_loop._required_tool_for_query("carikan berita perang us israel vs iran terbaru") == "web_search"
    assert agent_loop._required_tool_for_query("berita terbaru 2026 sekarang") == "web_search"
    assert agent_loop._required_tool_for_query("latest israel iran war 2026 now") == "web_search"
    assert (
        agent_loop._required_tool_for_query(
            "adakah gejolak politik sekarang? saya dengar ada perang iran vs us israel ya"
        )
        == "web_search"
    )
    assert agent_loop._required_tool_for_query("kenapa jawabnya gitu? kan saya cari berita") is None
    assert agent_loop._required_tool_for_query("hai") is None


def test_required_tool_for_query_detects_multilingual_weather_and_reminder(agent_loop):
    assert agent_loop._required_tool_for_query("เตือนฉันอีก 2 นาทีให้กินข้าว") == "cron"
    assert agent_loop._required_tool_for_query("อากาศกรุงเทพวันนี้") == "weather"
    assert agent_loop._required_tool_for_query("两分钟后提醒我吃饭") == "cron"
    assert agent_loop._required_tool_for_query("北京今天天气怎么样") == "weather"


def test_required_tool_for_query_prefers_cleanup_when_cleanup_intent_and_disk_terms_overlap(agent_loop):
    assert agent_loop._required_tool_for_query("bersihkan cache ssd pc sekarang") == "cleanup_system"
    assert agent_loop._required_tool_for_query("ya bersihkan cache agar free space lebih banyak") == "cleanup_system"
    assert agent_loop._required_tool_for_query("bersihkan space") == "cleanup_system"


def test_required_tool_for_query_detects_stock_from_explicit_tickers_without_stock_keyword(agent_loop):
    assert agent_loop._required_tool_for_query("bbri bbca bmri sekarang berapa") == "stock"
    assert agent_loop._required_tool_for_query("bbca.jk now") == "stock"
    assert agent_loop._required_tool_for_query("bank mandiri berapa sekarang") == "stock"
    assert agent_loop._required_tool_for_query("bank rakyat indonesia dan bank central asia") == "stock"
    assert agent_loop._required_tool_for_query("toyota sekarang berapa") == "stock"
    assert agent_loop._required_tool_for_query("トヨタ 株価 いくら") == "stock"
    assert agent_loop._required_tool_for_query("iya kamu bener") is None
    assert agent_loop._required_tool_for_query("umur kamu berapa sekarang") is None


def test_required_tool_for_query_tolerates_common_typos_for_core_intents(agent_loop):
    assert agent_loop._required_tool_for_query("ingatkn 2 menit lagi makan") == "cron"
    assert agent_loop._required_tool_for_query("temprature cilacap today") == "weather"
    assert agent_loop._required_tool_for_query("bersihkn cache ssd skrg") == "cleanup_system"
    assert agent_loop._required_tool_for_query("cek updat kabot sekarang") == "check_update"
    assert agent_loop._required_tool_for_query("disk cleenup now") == "cleanup_system"


def test_required_tool_for_query_detects_reminder_from_time_plus_action_without_explicit_keyword(agent_loop):
    assert agent_loop._required_tool_for_query("2 menit lagi makan") == "cron"
    assert agent_loop._required_tool_for_query("in 10 minutes stretch") == "cron"


def test_infer_required_tool_from_history_prefers_recent_substantive_user_intent(agent_loop):
    history = [
        {"role": "user", "content": "berita terbaru 2026 sekarang"},
        {"role": "assistant", "content": "balas ya kalau lanjut"},
        {"role": "user", "content": "bbri bbca bmri sekarang berapa"},
    ]

    tool, source = agent_loop._infer_required_tool_from_history("lanjut", history)

    assert tool == "stock"
    assert source == "bbri bbca bmri sekarang berapa"


def test_infer_required_tool_from_history_skips_low_information_user_turns(agent_loop):
    history = [
        {"role": "user", "content": "berita terbaru 2026 sekarang"},
        {"role": "assistant", "content": "balas ya kalau lanjut"},
        {"role": "user", "content": "ya"},
        {"role": "user", "content": "oke"},
    ]

    tool, source = agent_loop._infer_required_tool_from_history("lanjut", history)

    assert tool == "web_search"
    assert source == "berita terbaru 2026 sekarang"


def test_required_tool_for_query_keeps_sysinfo_for_non_cleanup_disk_query(agent_loop):
    assert agent_loop._required_tool_for_query("cek free space ssd sekarang") == "get_system_info"


def test_required_tool_for_query_supports_multilingual_cleanup_intent(agent_loop):
    assert agent_loop._required_tool_for_query("please clean up disk cache now") == "cleanup_system"
    assert agent_loop._required_tool_for_query("ล้างแคช พื้นที่ดิสก์ ตอนนี้") == "cleanup_system"
    assert agent_loop._required_tool_for_query("请清理磁盘空间并清除缓存") == "cleanup_system"


def test_required_tool_for_query_keeps_multilingual_sysinfo_without_cleanup_action(agent_loop):
    assert agent_loop._required_tool_for_query("พื้นที่ดิสก์คงเหลือเท่าไหร่") == "get_system_info"
    assert agent_loop._required_tool_for_query("磁盘空间剩余多少") == "get_system_info"


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
async def test_execute_required_tool_fallback_weather_prefers_fresh_raw_query_over_stale_resolved_query(agent_loop):
    execute_mock = AsyncMock(return_value="Cilacap: 27C, cerah")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="kalau suhu cilacap berapa sekarang",
        metadata={"required_tool_query": "berita terbaru 2026 sekarang"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("weather", msg)
    assert result == "Cilacap: 27C, cerah"
    execute_mock.assert_awaited_once_with(
        "weather",
        {"location": "Cilacap", "context_text": "kalau suhu cilacap berapa sekarang"},
    )


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_web_search_calls_search_tool(agent_loop):
    execute_mock = AsyncMock(return_value="1. Reuters ...")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="carikan berita perang us israel vs iran terbaru",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("web_search", msg)
    assert "Reuters" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "web_search"
    assert params["query"] == msg.content
    assert params["count"] == 5
    assert params["context_text"] == msg.content


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_web_search_uses_resolved_query_metadata(agent_loop):
    execute_mock = AsyncMock(return_value="1. Reuters ...")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="gas",
        metadata={"required_tool_query": "berita terbaru 2026 sekarang"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("web_search", msg)
    assert "Reuters" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "web_search"
    assert params["query"] == "berita terbaru 2026 sekarang"
    assert params["count"] == 5
    assert params["context_text"] == "berita terbaru 2026 sekarang"


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_web_search_ignores_verbose_stale_metadata_on_low_information_followup(agent_loop):
    execute_mock = AsyncMock(return_value="search-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="gas",
        metadata={
            "required_tool_query": (
                "Setuju, saya akan ambil sekarang. "
                "Berikut langkah yang akan saya lakukan: "
                "1) tarik data 2) rangkum 3) kirim link."
            )
        },
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("web_search", msg)
    assert result == i18n_t("web_search.need_topic", msg.content)
    execute_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_web_search_requires_query_when_empty(agent_loop):
    execute_mock = AsyncMock(return_value="search-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="   ",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("web_search", msg)
    assert result == i18n_t("web_search.need_query", msg.content)
    execute_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_check_update_formats_localized_summary(agent_loop):
    execute_mock = AsyncMock(
        return_value='{"update_available": true, "latest_version": "v0.5.9", "current_version": "0.5.8", "commits_behind": 1, "release_url": "https://example.com/release"}'
    )
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="cek update kabot sekarang",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("check_update", msg)
    assert "Update tersedia" in result
    assert "https://example.com/release" in result
    execute_mock.assert_awaited_once_with("check_update", {})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_system_update_formats_done_notification(agent_loop):
    execute_mock = AsyncMock(
        return_value='{"success": true, "updated_from": "0.5.8", "updated_to": "0.5.9", "restart_required": true, "notify_message": "Update completed."}'
    )
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="update kabot sekarang",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("system_update", msg)
    assert ("Berhasil update" in result) or ("Successfully updated" in result)
    assert ("Restart Kabot sekarang" in result) or ("Restart Kabot now" in result)
    execute_mock.assert_awaited_once_with("system_update", {"confirm_restart": False})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_extracts_lowercase_idx_tickers(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="kalau saham bbri bbca bmri berapa sekarang",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "BBRI.JK,BBCA.JK,BMRI.JK"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_prefers_fresh_raw_query_over_stale_resolved_query(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="kalau saham bbri bbca bmri berapa sekarang",
        metadata={"required_tool_query": "top 10 saham indonesia"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "BBRI.JK,BBCA.JK,BMRI.JK"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_short_followup_with_new_symbol_prefers_raw_text(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="adaro mana",
        metadata={"required_tool_query": "cek harga saham bbri bbca bmri"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "ADRO.JK"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_keeps_global_tickers_without_idx_suffix(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="stock aapl msft now",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "AAPL,MSFT"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_maps_common_idx_aliases(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="harga saham bca bri mandiri sekarang",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "BBCA.JK,BBRI.JK,BMRI.JK"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_maps_adaro_alias(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="cek harga saham bbri bbca bmri adaro",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "BBRI.JK,BBCA.JK,BMRI.JK,ADRO.JK"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_maps_phrase_aliases_for_novice_company_names(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content=(
            "cek harga bank rakyat indonesia, bank central asia, bank mandiri, "
            "bank negara indonesia, adaro energy indonesia, toba bara"
        ),
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with(
        "stock",
        {"symbol": "BBRI.JK,BBCA.JK,BMRI.JK,BBNI.JK,ADRO.JK,TOBA.JK"},
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
