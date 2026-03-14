"""Split from tests/agent/test_tool_enforcement.py to keep test modules below 1000 lines.
Chunk 1: test_required_tool_for_query_detects_weather_and_reminder .. test_execute_required_tool_fallback_stock_maps_phrase_aliases_for_novice_company_names.
"""

import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.cron_fallback_nlp import required_tool_for_query as cron_required_tool_for_query
from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.loop import AgentLoop
from kabot.agent.loop_core import tool_enforcement as tool_enforcement_module
from kabot.agent.loop_core.tool_enforcement_parts import action_requests as action_requests_module
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_path,
    _extract_message_delivery_path,
    _extract_read_file_path,
    _query_has_tool_payload,
    infer_action_required_tool_for_loop,
    execute_required_tool_fallback,
)
from kabot.agent.loop_core.tool_enforcement_parts.core import (
    _get_last_delivery_path,
    _get_last_navigated_path,
    _set_last_delivery_path,
)
from kabot.bus.events import InboundMessage
from kabot.bus.queue import MessageBus
from kabot.cron.service import CronService
from kabot.providers.base import LLMResponse
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

def test_required_tool_for_query_detects_weather_and_reminder(agent_loop):
    assert agent_loop._required_tool_for_query("tolong cek suhu cilacap hari ini") == "weather"
    assert agent_loop._required_tool_for_query("purwokerto berapa derajat sekarang") == "weather"
    assert agent_loop._required_tool_for_query("dibandung berangin apa ga") == "weather"
    assert (
        agent_loop._required_tool_for_query(
            "ya itu cek update real time kondisi cuaca, kecepatan angin, arah angin di bandung"
        )
        == "weather"
    )
    assert agent_loop._required_tool_for_query("ingatkan 2 menit lagi makan") == "cron"
    assert agent_loop._required_tool_for_query("tolong list jadwal reminder saya") == "cron"
    assert agent_loop._required_tool_for_query("cek update kabot sekarang") == "check_update"
    assert agent_loop._required_tool_for_query("update kabot sekarang") == "system_update"
    assert agent_loop._required_tool_for_query("kirim file tes.md") == "message"
    assert agent_loop._required_tool_for_query("cari file report.pdf lalu kirim ke chat ini") == "read_file"
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

def test_required_tool_for_query_keeps_meta_skill_and_workflow_prompts_ai_driven(agent_loop):
    assert agent_loop._required_tool_for_query("follow the weather workflow for this task") is None
    assert agent_loop._required_tool_for_query("tolong ikuti workflow cuaca untuk tugas ini") is None
    assert agent_loop._required_tool_for_query("please use the weather skill for this request") is None
    assert agent_loop._required_tool_for_query("tolong pakai skill weather untuk request ini ya") is None
    assert agent_loop._required_tool_for_query("tolong pakai skill weather untuk permintaan ini ya") is None
    assert agent_loop._required_tool_for_query("follow the writing plans workflow for this spec") is None
    assert agent_loop._required_tool_for_query("ikuti alur writing plans untuk spec ini") is None
    assert agent_loop._required_tool_for_query("请用 weather 技能处理这个请求。") is None
    assert agent_loop._required_tool_for_query("请用 cron 技能处理这个请求。") is None
    assert agent_loop._required_tool_for_query("请用 apple-reminders 技能处理这个请求。") is None
    assert agent_loop._required_tool_for_query("ช่วยใช้สกิล weather กับงานนี้หน่อย") is None
    assert agent_loop._required_tool_for_query("writing-plans スキルを使ってこの依頼を手伝って") is None

def test_required_tool_for_query_prefers_cleanup_when_cleanup_intent_and_disk_terms_overlap(agent_loop):
    assert agent_loop._required_tool_for_query("bersihkan cache ssd pc sekarang") == "cleanup_system"
    assert agent_loop._required_tool_for_query("ya bersihkan cache agar free space lebih banyak") == "cleanup_system"
    assert agent_loop._required_tool_for_query("bersihkan space") == "cleanup_system"

def test_agent_loop_registers_server_monitor_and_routes_runtime_status_followups(agent_loop):
    assert agent_loop.tools.has("server_monitor") is True
    assert agent_loop._required_tool_for_query("status server gimana") == "server_monitor"
    assert agent_loop._required_tool_for_query("ya cek status server sekarang") == "server_monitor"

def test_required_tool_for_query_detects_stock_from_explicit_tickers_without_stock_keyword(agent_loop):
    assert agent_loop._required_tool_for_query("bbri bbca bmri sekarang berapa") is None
    assert agent_loop._required_tool_for_query("bbca.jk now") is None
    assert agent_loop._required_tool_for_query("bank mandiri berapa sekarang") is None
    assert agent_loop._required_tool_for_query("bank rakyat indonesia dan bank central asia") is None
    assert agent_loop._required_tool_for_query("toyota sekarang berapa") is None
    assert agent_loop._required_tool_for_query("トヨタ 株価 いくら") is None
    assert agent_loop._required_tool_for_query("iya kamu bener") is None
    assert agent_loop._required_tool_for_query("umur kamu berapa sekarang") is None

def test_required_tool_for_query_detects_stock_tracking_and_fx_queries(agent_loop):
    assert agent_loop._required_tool_for_query("dalam 1 bulan terakhir gimana pergerakan saham bri nya") is None
    assert agent_loop._required_tool_for_query("track apple stock movement 3 months") is None
    assert agent_loop._required_tool_for_query("1 usd berapa rupiah sekarang") is None
    assert agent_loop._required_tool_for_query("kurs usd ke idr hari ini") is None
    assert agent_loop._required_tool_for_query("kalau dirupiahkan dengan harga sekarang berapa") is None
    assert (
        agent_loop._required_tool_for_query(
            "If Apple is around 260 dollars, roughly how much is that in Indonesian rupiah today?"
        )
        is None
    )
    assert agent_loop._required_tool_for_query("cenderung turun atau naik?") is None


def test_required_tool_for_query_prefers_matching_external_finance_skill_over_builtin_stock_crypto(agent_loop):
    skills_root = agent_loop.workspace / "skills" / "manus-stock-analysis"
    skills_root.mkdir(parents=True, exist_ok=True)
    (skills_root / "SKILL.md").write_text(
        "---\n"
        "name: manus-stock-analysis\n"
        'description: "Analyze stocks, crypto, market quotes, tickers, trends, and finance watchlists."\n'
        "---\n\n"
        "# Manus Stock Analysis\n",
        encoding="utf-8",
    )

    matches = agent_loop.context.skills.match_skills(
        "bbca bbri bmri adaro berapa sekarang",
        profile="GENERAL",
    )
    assert matches
    assert matches[0].startswith("manus-stock-analysis")

    assert agent_loop._required_tool_for_query("bbca bbri bmri adaro berapa sekarang") is None
    assert agent_loop._required_tool_for_query("harga btc terbaru") is None


def test_required_tool_for_query_suppresses_legacy_market_tools_when_external_finance_skill_exists(agent_loop):
    skills_root = agent_loop.workspace / "skills" / "stock-analysis"
    skills_root.mkdir(parents=True, exist_ok=True)
    (skills_root / "SKILL.md").write_text(
        "---\n"
        "name: stock-analysis\n"
        'description: "Analyze stocks, crypto, market trends, company research, and watchlists."\n'
        "---\n\n"
        "# Stock Analysis\n",
        encoding="utf-8",
    )

    assert agent_loop.context.skills.has_preferred_external_skill_match(
        "cek harga saham bca bri mandiri adaro",
        profile="GENERAL",
    )
    assert agent_loop._required_tool_for_query("cek harga saham bca bri mandiri adaro") is None
    assert agent_loop._required_tool_for_query("bandingkan saham bca bri mandiri adaro") is None

def test_required_tool_for_query_chat_mix_matrix(agent_loop):
    # End-to-end style routing expectations for common real-chat prompts.
    cases = [
        (
            "adakah gejolak politik sekarang? saya dengar ada perang iran vs us israel ya",
            "web_search",
        ),
        ("cek suhu purwokerto jawa tengah sekarang", "weather"),
        ("cek harga saham bbri bbca bmri adaro", None),
        ("harga btc terbaru", None),
        # Image/TTS should not be forced into deterministic stock/weather/cron paths.
        ("buatkan gambar mobil di hutan", None),
        ("tolong bacakan teks ini jadi suara", None),
        ("halo apa kabar", None),
    ]

    for prompt, expected in cases:
        assert agent_loop._required_tool_for_query(prompt) == expected

def test_required_tool_for_query_does_not_misclassify_file_or_stop_messages_as_stock(agent_loop):
    assert agent_loop._required_tool_for_query("baca file config.json") == "read_file"
    assert agent_loop._required_tool_for_query("config.json coba baca isinya") == "read_file"
    assert (
        agent_loop._required_tool_for_query(
            r"tolong baca file C:\\Users\\Arvy Kairi\\.kabot\\config.json"
        )
        == "read_file"
    )
    assert agent_loop._required_tool_for_query("tolong kirim email ke tim marketing") is None
    assert agent_loop._required_tool_for_query("cek email terbaru dari client") is None
    assert agent_loop._required_tool_for_query("buat draft email ke tim support") is None
    assert agent_loop._required_tool_for_query("bikin excel laporan penjualan bulan ini") is None
    assert agent_loop._required_tool_for_query("buat spreadsheet budget proyek xlsx") is None
    assert agent_loop._required_tool_for_query("buat file excel jadwal lari 8 minggu") is None
    assert (
        agent_loop._required_tool_for_query(
            "Aku akan buat file Excel jadwal lari 8 minggu kamu di workspace, lalu langsung kirim filenya ke chat ini."
        )
        is None
    )
    assert agent_loop._required_tool_for_query("stop bahas saham") is None
    assert agent_loop._required_tool_for_query("bukan tentang saham ini loh") is None
    assert agent_loop._required_tool_for_query("stop bahas cuaca") is None
    assert agent_loop._required_tool_for_query("jangan bahas crypto") is None
    assert agent_loop._required_tool_for_query("bukan tentang berita") is None
    assert agent_loop._required_tool_for_query("market cap bbca sekarang") is None


def test_required_tool_for_query_prefers_web_fetch_for_direct_page_requests(agent_loop):
    assert (
        agent_loop._required_tool_for_query("fetch https://example.com and summarize the page")
        == "web_fetch"
    )
    assert (
        agent_loop._required_tool_for_query("ambil isi website example.com lalu ringkas")
        == "web_fetch"
    )


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_supports_web_fetch_direct_url(agent_loop):
    tool_executor = AsyncMock(return_value="HTTP 200\n\n[EXTERNAL_CONTENT]\nBBCA page\n[/EXTERNAL_CONTENT]")
    agent_loop.tools.execute = tool_executor

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="finance.yahoo.com/quote/BBCA.JK",
    )

    result = await execute_required_tool_fallback(agent_loop, "web_fetch", msg)

    assert "BBCA page" in result
    tool_executor.assert_awaited_once_with(
        "web_fetch",
        {
            "url": "https://finance.yahoo.com/quote/BBCA.JK",
            "extract_mode": "markdown",
            "context_text": "finance.yahoo.com/quote/BBCA.JK",
        },
    )


def test_required_tool_for_query_does_not_route_general_knowledge_questions_to_stock(agent_loop):
    assert agent_loop._required_tool_for_query("JAM BERAPA") is None
    assert agent_loop._required_tool_for_query("jam berapa sekarang") is None
    assert agent_loop._required_tool_for_query("IQ MANUSIA BERAPA") is None
    assert agent_loop._required_tool_for_query("iq manusia berapa") is None
    assert agent_loop._required_tool_for_query("IQ MANUSIA RATA RATA BERAPA") is None
    assert agent_loop._required_tool_for_query("KALAU EQ MANUSIA BERAPA") is None
    assert agent_loop._required_tool_for_query("koneksi ke meta threads bisa?") is None
    assert agent_loop._required_tool_for_query("saya mau koneksi api meta threads") is None


def test_required_tool_for_query_does_not_route_personal_hr_zone_or_quoted_health_context_to_web_or_weather(agent_loop):
    assert (
        agent_loop._required_tool_for_query(
            "simpan di memory umurku sekarang 25 tahun kelahiran 16 juni 2000. tolong hitung zona hr personal"
        )
        is None
    )
    assert (
        agent_loop._required_tool_for_query(
            "umurku sekarang 25 tahun tolong hitung zona hr personal"
        )
        is None
    )
    quoted_health_context = """Iya, untuk laki-laki saat lari, HR (detak jantung) sering di atas 160 bpm itu belum tentu berbahaya, tergantung:

1. Umur
2. Level kebugaran
3. Durasi di HR tinggi
4. Ada gejala atau tidak (pusing, nyeri dada, sesak, berdebar tidak normal)

Patokan cepat
• Estimasi HR max kasar: 220 - usia
• Perhatikan tidur, hidrasi, kafein, suhu cuaca (semua bisa bikin HR naik)

Kalau kamu mau, aku bisa bantu hitung zona HR personal berdasarkan usia kamu dan target lari.

dari sini hitung hr zona saya umur 25 tahun"""
    assert agent_loop._required_tool_for_query(quoted_health_context) is None

def test_required_tool_for_query_does_not_treat_workspace_paths_as_system_info(agent_loop):
    assert (
        agent_loop._required_tool_for_query(
            r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini"
        )
        is None
    )
    assert (
        agent_loop._required_tool_for_query(
            "C:/Users/Arvy Kairi/.kabot/workspace/landing_hacker.html font pada web ini"
        )
        is None
    )


def test_required_tool_for_query_does_not_treat_verbose_upgrade_promise_with_arrow_controls_as_read_file(agent_loop):
    text = """Mantap, lanjut ya — aku akan upgrade game yang tadi dengan 4 fitur ini sekaligus:

1) 2-player mode (P1: W/S, P2: ↑/↓)
2) Mobile touch controls
3) Sound effects
4) Difficulty levels (Easy/Medium/Hard)

Aku akan edit file ping-pong/index.html, ping-pong/style.css, dan ping-pong/game.js sekarang. Setelah itu aku kabarin kalau sudah selesai."""

    assert agent_loop._required_tool_for_query(text) is None

def test_required_tool_for_query_does_not_force_cleanup_or_sysinfo_for_large_file_scan_requests(agent_loop):
    assert (
        agent_loop._required_tool_for_query(
            "cari file/folder yang ukurannya besar, karena ssd 256gb sisanya cuma 18gb an"
        )
        is None
    )
    assert (
        agent_loop._required_tool_for_query(
            "mantap sekali, kalau untuk file atau folder yang ukurannya besar ada ga? coba periksa"
        )
        is None
    )

def test_required_tool_for_query_routes_directory_listing_queries_to_list_dir(agent_loop):
    assert agent_loop._required_tool_for_query("cek file/folder di desktop isinya apa aja") == "list_dir"
    assert agent_loop._required_tool_for_query("tolong masuk ke desktop di pc") == "list_dir"
    assert agent_loop._required_tool_for_query(r"tampilkan isi folder C:\Users\Arvy Kairi\Desktop\bot") == "list_dir"
    assert agent_loop._required_tool_for_query("tampilkan isi folder /var/log") == "list_dir"

def test_required_tool_for_query_routes_multilingual_directory_listing_queries_to_list_dir(agent_loop):
    assert agent_loop._required_tool_for_query("显示桌面文件夹内容") == "list_dir"
    assert agent_loop._required_tool_for_query("デスクトップフォルダを表示して") == "list_dir"
    assert agent_loop._required_tool_for_query("เปิดโฟลเดอร์เดสก์ท็อป") == "list_dir"
    assert agent_loop._required_tool_for_query("显示 文件夹 bot") == "list_dir"
    assert agent_loop._required_tool_for_query("表示 フォルダ bot") == "list_dir"
    assert agent_loop._required_tool_for_query("เปิด โฟลเดอร์ bot") == "list_dir"

def test_filesystem_extractors_support_directory_queries_without_false_read_file_path(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))
    expected_desktop = str(tool_enforcement_module.Path("/Users/Arvy Kairi") / "Desktop")

    assert _extract_read_file_path("cek file/folder di desktop isinya apa aja") is None
    assert _extract_list_dir_path("cek file/folder di desktop isinya apa aja") == expected_desktop
    assert _extract_list_dir_path(r"tampilkan isi folder C:\Users\Arvy Kairi\Desktop\bot") == r"C:\Users\Arvy Kairi\Desktop\bot"
    assert _extract_list_dir_path("tampilkan isi folder /var/log") == "/var/log"

def test_extract_read_file_path_trims_trailing_natural_language_after_file_extension():
    assert (
        _extract_read_file_path(
            r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html font pada web ini"
        )
        == r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html"
    )
    assert (
        _extract_read_file_path(
            "C:/Users/Arvy Kairi/.kabot/workspace/landing_hacker.html what font is this"
        )
        == "C:/Users/Arvy Kairi/.kabot/workspace/landing_hacker.html"
    )
    assert (
        _extract_read_file_path(
            "buat file .smoke_tmp/smoke_action_request.txt di workspace berisi HALO_KABOT"
        )
        == ".smoke_tmp/smoke_action_request.txt"
    )


def test_extract_read_file_path_does_not_treat_arrow_key_controls_as_filesystem_paths():
    assert _extract_read_file_path("2-player mode (P1: W/S, P2: ↑/↓)") is None


def test_extract_read_file_path_does_not_treat_letter_slash_letter_controls_as_filesystem_paths():
    assert _extract_read_file_path("2-player mode (P1: W/S, P2: A/D)") is None
    assert _extract_read_file_path("controls: W/S vs A/D") is None


def test_extract_read_file_path_prefers_real_relative_file_path_over_arrow_key_controls():
    text = """Mantap, lanjut ya — aku akan upgrade game yang tadi dengan 4 fitur ini sekaligus:

1) 2-player mode (P1: W/S, P2: ↑/↓)
2) Mobile touch controls
3) Sound effects
4) Difficulty levels (Easy/Medium/Hard)

Aku akan edit file ping-pong/index.html, ping-pong/style.css, dan ping-pong/game.js sekarang. Setelah itu aku kabarin kalau sudah selesai."""

    assert _extract_read_file_path(text) == "ping-pong/index.html"

def test_filesystem_extractors_support_multilingual_directory_aliases(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))
    expected_desktop = str(tool_enforcement_module.Path("/Users/Arvy Kairi") / "Desktop")
    expected_downloads = str(tool_enforcement_module.Path("/Users/Arvy Kairi") / "Downloads")

    assert _extract_list_dir_path("显示桌面文件夹内容") == expected_desktop
    assert _extract_list_dir_path("デスクトップフォルダを表示して") == expected_desktop
    assert _extract_list_dir_path("เปิดโฟลเดอร์เดสก์ท็อป") == expected_desktop
    assert _extract_list_dir_path("显示下载文件夹") == expected_downloads
    assert _extract_list_dir_path("显示 文件夹 bot", last_tool_context={"path": expected_desktop}) == str(tool_enforcement_module.Path(expected_desktop) / "bot")
    assert _extract_list_dir_path("表示 フォルダ bot", last_tool_context={"path": expected_desktop}) == str(tool_enforcement_module.Path(expected_desktop) / "bot")
    assert _extract_list_dir_path("เปิด โฟลเดอร์ bot", last_tool_context={"path": expected_desktop}) == str(tool_enforcement_module.Path(expected_desktop) / "bot")

def test_query_has_tool_payload_treats_multilingual_relative_folder_turns_as_new_list_dir_payload():
    assert _query_has_tool_payload("list_dir", "显示 文件夹 bot") is True
    assert _query_has_tool_payload("list_dir", "表示 フォルダ bot") is True
    assert _query_has_tool_payload("list_dir", "เปิด โฟลเดอร์ bot") is True


def test_query_has_tool_payload_requires_exact_symbols_for_legacy_stock_tools():
    assert _query_has_tool_payload("stock", "cek harga saham bca bri mandiri adaro sekarang") is False
    assert _query_has_tool_payload("stock_analysis", "bandingkan saham apple microsoft sekarang") is False
    assert _query_has_tool_payload("stock", "BBCA.JK BBRI.JK BMRI.JK ADRO.JK") is True
    assert _query_has_tool_payload("stock_analysis", "AAPL MSFT trend 3 months") is True

def test_required_tool_for_query_tolerates_common_typos_for_core_intents(agent_loop):
    assert agent_loop._required_tool_for_query("ingatkn 2 menit lagi makan") == "cron"
    assert agent_loop._required_tool_for_query("temprature cilacap today") == "weather"
    assert agent_loop._required_tool_for_query("bersihkn cache ssd skrg") == "cleanup_system"
    assert agent_loop._required_tool_for_query("cek updat kabot sekarang") == "check_update"
    assert agent_loop._required_tool_for_query("disk cleenup now") == "cleanup_system"


def test_infer_action_required_tool_for_loop_infers_find_files_for_search_request():
    loop = SimpleNamespace(
        tools=SimpleNamespace(
            has=lambda name: name == "find_files",
            tool_names=["find_files"],
        )
    )

    tool_name, source = infer_action_required_tool_for_loop(
        loop,
        "cari file report.pdf di server ini",
    )

    assert tool_name == "find_files"
    assert source == "cari file report.pdf di server ini"


def test_infer_action_required_tool_for_loop_infers_message_for_explicit_send_file_request():
    loop = SimpleNamespace(
        tools=SimpleNamespace(
            has=lambda name: name == "message",
            tool_names=["message"],
        )
    )

    tool_name, source = infer_action_required_tool_for_loop(
        loop,
        r"kirim file C:\Users\Arvy Kairi\Desktop\report.pdf ke chat ini",
    )

    assert tool_name == "message"
    assert source == r"kirim file C:\Users\Arvy Kairi\Desktop\report.pdf ke chat ini"


def test_infer_action_required_tool_for_loop_infers_message_for_bare_filename_send_request():
    loop = SimpleNamespace(
        tools=SimpleNamespace(
            has=lambda name: name == "message",
            tool_names=["message"],
        )
    )

    tool_name, source = infer_action_required_tool_for_loop(
        loop,
        "kirim file TELEGRAM_DEMO.md kesini",
    )

    assert tool_name == "message"
    assert source == "kirim file TELEGRAM_DEMO.md kesini"


def test_infer_action_required_tool_for_loop_keeps_find_files_for_search_then_send_phrase():
    loop = SimpleNamespace(
        tools=SimpleNamespace(
            has=lambda name: name in {"find_files", "message"},
            tool_names=["find_files", "message"],
        )
    )

    tool_name, source = infer_action_required_tool_for_loop(
        loop,
        "cari file report.pdf lalu kirim ke chat ini",
    )

    assert tool_name == "find_files"
    assert source == "cari file report.pdf lalu kirim ke chat ini"


def test_infer_action_required_tool_for_loop_does_not_force_message_for_howto_send_phrase():
    loop = SimpleNamespace(
        tools=SimpleNamespace(
            has=lambda name: name in {"message", "web_search"},
            tool_names=["message", "web_search"],
        )
    )

    tool_name, source = infer_action_required_tool_for_loop(
        loop,
        "cara kirim file tes.md lewat python",
    )

    assert tool_name is None
    assert source is None


def test_infer_action_required_tool_for_loop_prefers_write_file_for_create_then_send_request():
    loop = SimpleNamespace(
        tools=SimpleNamespace(
            has=lambda name: name in {"write_file", "message"},
            tool_names=["write_file", "message"],
        )
    )

    tool_name, source = infer_action_required_tool_for_loop(
        loop,
        "buat file .smoke_tmp/report.txt berisi HALO lalu kirim ke chat ini",
    )

    assert tool_name == "write_file"
    assert source == "buat file .smoke_tmp/report.txt berisi HALO lalu kirim ke chat ini"


def test_infer_action_required_tool_for_loop_does_not_force_write_file_for_path_only_code_authoring_request():
    loop = SimpleNamespace(
        tools=SimpleNamespace(
            has=lambda name: name == "write_file",
            tool_names=["write_file"],
        )
    )

    tool_name, source = infer_action_required_tool_for_loop(
        loop,
        "buat file src/index.html untuk landing page payment gateway dark style crypto",
    )

    assert tool_name is None
    assert source is None

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

    assert tool == "web_search"
    assert source == "berita terbaru 2026 sekarang"

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

def test_infer_required_tool_from_history_skips_generic_contextual_plan_followup(agent_loop):
    history = [
        {"role": "user", "content": "kalau saham apple berapa sekarang"},
        {
            "role": "assistant",
            "content": (
                "Kalau kamu mau, aku bisa lanjut bikin rencana entry-exit 3 skenario "
                "(breakout, pullback, dan invalidation) lengkap angka levelnya."
            ),
        },
    ]

    tool, source = agent_loop._infer_required_tool_from_history("lanjut rencana", history)

    assert tool is None
    assert source is None


def test_required_tool_for_query_prefers_stock_analysis_for_trade_plan_requests(agent_loop):
    assert (
        agent_loop._required_tool_for_query(
            "Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation"
        )
        is None
    )
    assert (
        agent_loop._required_tool_for_query(
            "buatkan rencana entry exit aapl dengan support resistance dan stop loss"
        )
        is None
    )

def test_required_tool_for_query_keeps_sysinfo_for_non_cleanup_disk_query(agent_loop):
    assert agent_loop._required_tool_for_query("cek free space ssd sekarang") == "get_system_info"

def test_required_tool_for_query_supports_multilingual_cleanup_intent(agent_loop):
    assert agent_loop._required_tool_for_query("please clean up disk cache now") == "cleanup_system"
    assert agent_loop._required_tool_for_query("ล้างแคช พื้นที่ดิสก์ ตอนนี้") == "cleanup_system"
    assert agent_loop._required_tool_for_query("请清理磁盘空间并清除缓存") == "cleanup_system"

def test_required_tool_for_query_keeps_multilingual_sysinfo_without_cleanup_action(agent_loop):
    assert agent_loop._required_tool_for_query("พื้นที่ดิสก์คงเหลือเท่าไหร่") == "get_system_info"
    assert agent_loop._required_tool_for_query("磁盘空间剩余多少") == "get_system_info"


def test_required_tool_for_query_prefers_server_monitor_for_runtime_status_prompts():
    for prompt in (
        "status server gimana",
        "ya cek status server sekarang",
        "status server vps kabot",
        "bukan web, tapi status server yang dipake kamu",
    ):
        assert (
            cron_required_tool_for_query(
                prompt,
                has_weather_tool=True,
                has_cron_tool=True,
                has_system_info_tool=True,
                has_server_monitor_tool=True,
                has_web_search_tool=True,
            )
            == "server_monitor"
        )


def test_required_tool_for_query_detects_natural_process_inspection_prompts():
    for text in (
        "cek langsung proses yang paling makan CPU/RAM di perangkat ini",
        "proses yang paling makan cpu ram",
        "cek proses teratas yang makan resource",
    ):
        assert (
            cron_required_tool_for_query(
                text,
                has_weather_tool=False,
                has_cron_tool=False,
                has_process_memory_tool=True,
                has_server_monitor_tool=True,
            )
            == "get_process_memory"
        )


def test_required_tool_for_query_routes_memory_commit_to_save_memory_not_process_memory():
    assert (
        cron_required_tool_for_query(
            "I already told you to call me Maha Raja, please save this to memory",
            has_weather_tool=False,
            has_cron_tool=False,
            has_process_memory_tool=True,
            has_save_memory_tool=True,
        )
        == "save_memory"
    )
    assert (
        cron_required_tool_for_query(
            "please save this to memory",
            has_weather_tool=False,
            has_cron_tool=False,
            has_process_memory_tool=True,
            has_save_memory_tool=True,
        )
        == "save_memory"
    )

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
async def test_execute_required_tool_fallback_read_file_calls_read_file_tool(agent_loop):
    execute_mock = AsyncMock(return_value='{"providers": {"openai": {"api_key": "***"}}}')
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="baca file config.json",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("read_file", msg)
    assert "providers" in result
    execute_mock.assert_awaited_once_with("read_file", {"path": "config.json"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_read_file_prefers_active_working_directory_for_bare_filename(
    agent_loop,
):
    execute_mock = AsyncMock(return_value='{"providers": {"openai": {"api_key": "***"}}}')
    agent_loop.tools.execute = execute_mock
    kabot_dir = agent_loop.workspace / ".kabot"
    kabot_dir.mkdir(parents=True, exist_ok=True)
    config_path = kabot_dir / "config.json"
    config_path.write_text('{"providers": {"openai": {"api_key": "***"}}}', encoding="utf-8")

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="buka config.json",
        metadata={"working_directory": str(kabot_dir.resolve())},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("read_file", msg)

    assert "providers" in result
    execute_mock.assert_awaited_once_with("read_file", {"path": str(config_path.resolve())})
    assert msg.metadata.get("working_directory") == str(kabot_dir.resolve())


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_read_file_uses_resolved_workspace_path_when_file_exists(
    agent_loop,
):
    execute_mock = AsyncMock(return_value='{"providers": {"openai": {"api_key": "***"}}}')
    agent_loop.tools.execute = execute_mock
    config_path = agent_loop.workspace / "config.json"
    config_path.write_text('{"providers": {"openai": {"api_key": "***"}}}', encoding="utf-8")

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="buka config.json",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("read_file", msg)

    assert "providers" in result
    execute_mock.assert_awaited_once_with("read_file", {"path": str(config_path.resolve())})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_read_file_uses_session_working_directory_for_bare_filename(
    agent_loop,
):
    execute_mock = AsyncMock(return_value='{"embedding_model": "all-MiniLM-L6-v2"}')
    agent_loop.tools.execute = execute_mock
    kabot_dir = agent_loop.workspace / ".kabot"
    kabot_dir.mkdir(parents=True, exist_ok=True)
    config_path = kabot_dir / "config.json"
    config_path.write_text('{"embedding_model": "all-MiniLM-L6-v2"}', encoding="utf-8")

    session = agent_loop.sessions.get_or_create("telegram:chat-1")
    session.metadata["working_directory"] = str(kabot_dir.resolve())

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="buka config.json",
        metadata={},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("read_file", msg)

    assert "all-MiniLM-L6-v2" in result
    execute_mock.assert_awaited_once_with("read_file", {"path": str(config_path.resolve())})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_read_file_uses_last_file_context_path(agent_loop):
    execute_mock = AsyncMock(return_value="<html>...</html>")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="buka html ini",
        timestamp=datetime.now(),
        metadata={
            "last_tool_context": {
                "tool": "read_file",
                "path": r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html",
            }
        },
    )

    result = await agent_loop._execute_required_tool_fallback("read_file", msg)
    assert "<html>" in result
    execute_mock.assert_awaited_once_with(
        "read_file",
        {"path": r"C:\Users\Arvy Kairi\.kabot\workspace\landing_hacker.html"},
    )


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_write_file_creates_dot_relative_artifact(tmp_path):
    async def _exec_tool(name: str, payload: dict[str, str], session_key: str | None = None):
        assert name == "write_file"
        target = tmp_path / str(payload["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(payload["content"]), encoding="utf-8")
        return f"Successfully wrote {len(str(payload['content']))} bytes to {payload['path']}"

    loop = SimpleNamespace(
        _execute_tool=_exec_tool,
        tools=SimpleNamespace(execute=AsyncMock()),
    )
    content = "buat file .smoke_tmp/smoke_action_request.txt di workspace berisi HALO_KABOT"
    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=content,
        metadata={"required_tool_query": content},
    )

    result = await execute_required_tool_fallback(loop, "write_file", msg)

    assert "successfully wrote" in result.lower()
    assert (tmp_path / ".smoke_tmp" / "smoke_action_request.txt").read_text(encoding="utf-8") == "HALO_KABOT"


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_find_files_calls_find_files_tool(agent_loop):
    execute_mock = AsyncMock(return_value="FILE report.pdf")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cari file report.pdf",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("find_files", msg)

    assert result == "FILE report.pdf"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "find_files"
    assert params["query"] == "report.pdf"
    assert params["context_text"] == "cari file report.pdf"


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_find_files_uses_current_working_directory_phrase(
    agent_loop,
    tmp_path,
    monkeypatch,
):
    execute_mock = AsyncMock(return_value="FILE C:/tmp/report.pdf")
    agent_loop.tools.execute = execute_mock
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cari file report.pdf di folder kerja saat ini lalu kirim ke chat ini",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("find_files", msg)

    assert result == "FILE C:/tmp/report.pdf"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "find_files"
    assert params["query"] == "report.pdf"
    assert params["path"] == str(cwd.resolve())


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_find_files_prefers_last_navigated_path_as_root(agent_loop):
    execute_mock = AsyncMock(return_value="FILE C:/Users/Arvy Kairi/Desktop/bot/tes.md")
    agent_loop.tools.execute = execute_mock
    nav_dir = agent_loop.workspace
    nav_dir.mkdir(parents=True, exist_ok=True)

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cari file tes.md",
        metadata={"last_navigated_path": str(nav_dir.resolve())},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("find_files", msg)

    assert "tes.md" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "find_files"
    assert params["query"] == "tes.md"
    assert params["path"] == str(nav_dir.resolve())


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_find_files_prefers_working_directory_as_root(agent_loop):
    execute_mock = AsyncMock(return_value="FILE C:/Users/Arvy Kairi/Desktop/bot/tes.md")
    agent_loop.tools.execute = execute_mock
    working_dir = agent_loop.workspace
    working_dir.mkdir(parents=True, exist_ok=True)

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="cari file tes.md",
        metadata={"working_directory": str(working_dir.resolve())},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("find_files", msg)

    assert "tes.md" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "find_files"
    assert params["query"] == "tes.md"
    assert params["path"] == str(working_dir.resolve())


def test_resolve_find_files_root_prefers_last_tool_context_path_over_stale_last_navigated_path(agent_loop):
    active_dir = agent_loop.workspace / "active"
    stale_dir = agent_loop.workspace / "stale"
    active_dir.mkdir(parents=True, exist_ok=True)
    stale_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "last_tool_context": {"tool": "list_dir", "path": str(active_dir.resolve())},
        "last_navigated_path": str(stale_dir.resolve()),
    }

    resolved = action_requests_module._resolve_find_files_root(
        agent_loop,
        "find report.pdf",
        metadata=metadata,
    )

    assert resolved == str(active_dir.resolve())


def test_filesystem_resolve_find_files_root_prefers_last_tool_context_path_over_stale_last_navigated_path(tmp_path):
    from kabot.agent.loop_core.tool_enforcement_parts import filesystem_paths as filesystem_paths_module

    active_dir = tmp_path / "active"
    stale_dir = tmp_path / "stale"
    active_dir.mkdir(parents=True, exist_ok=True)
    stale_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "last_tool_context": {"tool": "list_dir", "path": str(active_dir.resolve())},
        "last_navigated_path": str(stale_dir.resolve()),
    }

    resolved = filesystem_paths_module._resolve_find_files_root(
        loop=SimpleNamespace(workspace=tmp_path),
        text="find report.pdf",
        metadata=metadata,
    )

    assert resolved == str(active_dir.resolve())


def test_get_last_navigated_path_prefers_working_directory_over_stale_breadcrumb(agent_loop):
    active_dir = agent_loop.workspace / "active"
    stale_dir = agent_loop.workspace / "stale"
    active_dir.mkdir(parents=True, exist_ok=True)
    stale_dir.mkdir(parents=True, exist_ok=True)

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="send the file",
        metadata={
            "working_directory": str(active_dir.resolve()),
            "last_navigated_path": str(stale_dir.resolve()),
        },
        timestamp=datetime.now(),
    )

    assert _get_last_navigated_path(agent_loop, msg, msg.metadata) == str(active_dir.resolve())


def test_get_last_navigated_path_prefers_session_breadcrumb_over_active_turn_breadcrumb(agent_loop):
    live_dir = agent_loop.workspace / "live-nav"
    stale_dir = agent_loop.workspace / "stale-nav"
    live_dir.mkdir(parents=True, exist_ok=True)
    stale_dir.mkdir(parents=True, exist_ok=True)

    session = agent_loop.sessions.get_or_create("telegram:chat-1")
    session.metadata["last_navigated_path"] = str(live_dir.resolve())

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="open it",
        metadata={"last_navigated_path": str(stale_dir.resolve())},
        timestamp=datetime.now(),
    )

    assert _get_last_navigated_path(agent_loop, msg, msg.metadata) == str(live_dir.resolve())


def test_get_last_delivery_path_prefers_session_delivery_over_active_turn_breadcrumb(agent_loop):
    live_file = agent_loop.workspace / "live" / "report.pdf"
    stale_file = agent_loop.workspace / "stale" / "report.pdf"
    live_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_text("live", encoding="utf-8")
    stale_file.write_text("stale", encoding="utf-8")

    session = agent_loop.sessions.get_or_create("telegram:chat-1")
    session.metadata["last_delivery_path"] = str(live_file.resolve())

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="send it",
        metadata={"last_delivery_path": str(stale_file.resolve())},
        timestamp=datetime.now(),
    )

    assert _get_last_delivery_path(agent_loop, msg, msg.metadata) == str(live_file.resolve())


def test_set_last_delivery_path_keeps_delivery_path_session_local_and_updates_cwd(agent_loop):
    delivery_dir = agent_loop.workspace / "desktop" / "bot"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    delivery_file = delivery_dir / "tes.md"
    delivery_file.write_text("demo", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key="telegram:chat-1",
        content="send it",
        metadata={},
    )

    normalized = _set_last_delivery_path(agent_loop, msg, msg.metadata, str(delivery_file.resolve()))
    session = agent_loop.sessions.get_or_create("telegram:chat-1")

    assert normalized == str(delivery_file.resolve())
    assert msg.metadata.get("working_directory") == str(delivery_dir.resolve())
    assert msg.metadata.get("last_delivery_path") is None
    assert session.metadata.get("last_delivery_path") == str(delivery_file.resolve())


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_read_file_uses_list_dir_when_last_context_is_directory(agent_loop):
    execute_mock = AsyncMock(return_value="📄 README.md\n📄 pyproject.toml")
    agent_loop.tools.execute = execute_mock
    project_dir = agent_loop.workspace / "waton"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "README.md").write_text("demo", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="baca seluruh file, aplikasi apa ini",
        metadata={"last_tool_context": {"tool": "list_dir", "path": str(project_dir.resolve())}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("read_file", msg)

    assert "README.md" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "list_dir"
    assert params["path"] == str(project_dir.resolve())


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_sends_explicit_file_path(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    report_path = agent_loop.workspace / "report.pdf"
    report_path.write_text("hello", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=f"kirim file {report_path} ke chat ini",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]
    assert params["content"]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_prefers_existing_cwd_relative_path(
    agent_loop,
    tmp_path,
    monkeypatch,
):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    relative_path = ".smoke_tmp/report.pdf"
    report_path = cwd / ".smoke_tmp" / "report.pdf"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("hello-from-cwd", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content=f"kirim file {relative_path} ke chat ini",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]
    assert params["content"]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_prefers_last_found_path_over_bare_filename(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    report_path = agent_loop.workspace / ".smoke_tmp" / "report.pdf"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("hello", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="kirim file report.pdf ke chat ini",
        metadata={"last_tool_context": {"tool": "find_files", "path": str(report_path.resolve())}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_resolves_bare_filename_inside_last_opened_folder(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    report_path = agent_loop.workspace / ".smoke_tmp" / "TELEGRAM_DEMO.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("demo", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="kirim file TELEGRAM_DEMO.md kesini",
        metadata={"last_tool_context": {"tool": "list_dir", "path": str(report_path.parent.resolve())}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_rejects_internal_temp_file_when_navigated_folder_missing_target(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock

    nav_dir = agent_loop.workspace / "desktop" / "bot"
    nav_dir.mkdir(parents=True, exist_ok=True)

    stale_dir = agent_loop.workspace / ".basetemp"
    stale_dir.mkdir(parents=True, exist_ok=True)
    stale_file = stale_dir / "tes.md"
    stale_file.write_text("stale", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="kirim file tes.md ke sini",
        metadata={
            "last_tool_context": {"tool": "list_dir", "path": str(stale_dir.resolve())},
            "last_navigated_path": str(nav_dir.resolve()),
        },
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    expected_candidate = str((nav_dir / "tes.md").resolve())
    assert result == i18n_t("filesystem.file_not_found", expected_candidate, path=expected_candidate)
    execute_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_multiturn_send_reuses_navigation_then_last_delivery(agent_loop):
    payloads: list[tuple[str, dict[str, object]]] = []

    async def _exec(name: str, payload: dict[str, object]):
        payloads.append((name, payload))
        if name == "list_dir":
            return "📄 tes.md"
        if name == "message":
            return "Message sent to telegram:chat-1"
        return "ok"

    agent_loop.tools.execute = AsyncMock(side_effect=_exec)

    nav_dir = agent_loop.workspace / "desktop" / "bot"
    nav_dir.mkdir(parents=True, exist_ok=True)
    target_file = nav_dir / "tes.md"
    target_file.write_text("demo", encoding="utf-8")

    session_key = "telegram:chat-1"

    msg1 = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key=session_key,
        content=f"buka {nav_dir}",
        metadata={},
        timestamp=datetime.now(),
    )
    await agent_loop._execute_required_tool_fallback("list_dir", msg1)

    session = agent_loop.sessions.get_or_create(session_key)
    assert session.metadata.get("working_directory") == str(nav_dir.resolve())
    assert session.metadata.get("last_navigated_path") is None

    msg2 = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key=session_key,
        content="kirim file tes.md ke sini",
        metadata={},
        timestamp=datetime.now(),
    )
    result2 = await agent_loop._execute_required_tool_fallback("message", msg2)
    assert result2 == "Message sent to telegram:chat-1"
    assert session.metadata.get("last_delivery_path") == str(target_file.resolve())

    msg3 = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key=session_key,
        content="kirim langsung",
        metadata={},
        timestamp=datetime.now(),
    )
    result3 = await agent_loop._execute_required_tool_fallback("message", msg3)
    assert result3 == "Message sent to telegram:chat-1"

    message_payloads = [p for name, p in payloads if name == "message"]
    assert len(message_payloads) == 2
    assert message_payloads[0]["files"] == [str(target_file.resolve())]
    assert message_payloads[1]["files"] == [str(target_file.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_send_without_target_uses_session_last_delivery_path(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock

    delivery_dir = agent_loop.workspace / "desktop" / "bot"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    delivery_file = delivery_dir / "tes.md"
    delivery_file.write_text("content", encoding="utf-8")

    session_key = "telegram:chat-1"
    session = agent_loop.sessions.get_or_create(session_key)
    session.metadata["last_delivery_path"] = str(delivery_file.resolve())

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key=session_key,
        content="kirim langsung",
        metadata={},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(delivery_file.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_prefers_session_last_navigated_path_when_message_metadata_missing(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    report_dir = agent_loop.workspace / "desktop" / "bot"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "tes.md"
    report_path.write_text("demo", encoding="utf-8")

    session_key = "telegram:chat-1"
    session = agent_loop.sessions.get_or_create(session_key)
    session.metadata["last_navigated_path"] = str(report_dir.resolve())

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key=session_key,
        content="kirim file tes.md ke sini",
        metadata={"last_tool_context": {"tool": "list_dir", "path": str((agent_loop.workspace / ".basetemp").resolve())}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_prefers_last_navigated_path_when_last_tool_path_is_stale(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    report_dir = agent_loop.workspace / "desktop" / "bot"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "tes.md"
    report_path.write_text("demo", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="kirim file tes.md ke sini",
        metadata={
            "last_tool_context": {"tool": "list_dir", "path": str((agent_loop.workspace / ".basetemp").resolve())},
            "last_navigated_path": str(report_dir.resolve()),
        },
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_prefers_last_navigated_path_for_bare_send_without_delivery_suffix(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    report_dir = agent_loop.workspace / "desktop" / "bot"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "tes.md"
    report_path.write_text("demo", encoding="utf-8")

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="kirim file tes.md",
        metadata={
            "last_tool_context": {"tool": "list_dir", "path": str((agent_loop.workspace / ".basetemp").resolve())},
            "last_navigated_path": str(report_dir.resolve()),
        },
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_prefers_session_last_navigated_path_for_bare_send(agent_loop):
    execute_mock = AsyncMock(return_value="Message sent to telegram:chat-1")
    agent_loop.tools.execute = execute_mock
    report_dir = agent_loop.workspace / "desktop" / "bot"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "tes.md"
    report_path.write_text("demo", encoding="utf-8")

    session_key = "telegram:chat-1"
    session = agent_loop.sessions.get_or_create(session_key)
    session.metadata["last_navigated_path"] = str(report_dir.resolve())

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        _session_key=session_key,
        content="kirim file tes.md",
        metadata={"last_tool_context": {"tool": "list_dir", "path": str((agent_loop.workspace / ".basetemp").resolve())}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "message"
    assert params["files"] == [str(report_path.resolve())]


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_message_archives_directory_before_sending(agent_loop):
    execute_mock = AsyncMock()
    agent_loop.tools.execute = execute_mock
    reports_dir = agent_loop.workspace / ".smoke_tmp" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "summary.txt").write_text("hello", encoding="utf-8")
    archive_path = agent_loop.workspace / ".smoke_tmp" / "reports.zip"
    archive_path.write_text("zip-placeholder", encoding="utf-8")

    async def _execute(tool_name, params, **_kwargs):
        if tool_name == "archive_path":
            return f"Created archive {archive_path.resolve()} from {reports_dir.resolve()}"
        if tool_name == "message":
            return "Message sent to telegram:chat-1"
        raise AssertionError(f"unexpected tool {tool_name}")

    execute_mock.side_effect = _execute

    msg = InboundMessage(
        channel="telegram",
        chat_id="chat-1",
        sender_id="user-1",
        content="kirim folder .smoke_tmp/reports ke chat ini",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("message", msg)

    assert result == "Message sent to telegram:chat-1"
    assert execute_mock.await_args_list[0].args[0] == "archive_path"
    assert execute_mock.await_args_list[1].args[0] == "message"
    assert execute_mock.await_args_list[1].args[1]["files"] == [str(archive_path.resolve())]
    assert execute_mock.await_args_list[1].args[1]["content"]

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_uses_platform_aliases_and_followup_context(agent_loop, monkeypatch):
    execute_mock = AsyncMock(return_value="📁 bot\n📁 reference-repo")
    agent_loop.tools.execute = execute_mock
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))
    expected_desktop = str(tool_enforcement_module.Path("/Users/Arvy Kairi") / "Desktop")

    first_msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="cek file/folder di desktop isinya apa aja",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("list_dir", first_msg)
    assert "bot" in result
    execute_mock.assert_awaited_once_with("list_dir", {"path": expected_desktop})

    execute_mock.reset_mock()
    followup_msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="ya tampilkan",
        metadata={"last_tool_context": {"path": expected_desktop}},
        timestamp=datetime.now(),
    )

    followup_result = await agent_loop._execute_required_tool_fallback("list_dir", followup_msg)
    assert "bot" in followup_result
    execute_mock.assert_awaited_once_with("list_dir", {"path": expected_desktop})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_prefers_xdg_special_directory_override(
    agent_loop,
    monkeypatch,
    tmp_path,
):
    execute_mock = AsyncMock(return_value="notes.txt")
    agent_loop.tools.execute = execute_mock
    fake_home = tmp_path / "home"
    user_dirs = fake_home / ".config" / "user-dirs.dirs"
    user_dirs.parent.mkdir(parents=True, exist_ok=True)
    user_dirs.write_text('XDG_DESKTOP_DIR="$HOME/Work/DesktopSpace"\n', encoding="utf-8")
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: fake_home)
    monkeypatch.delenv("XDG_DESKTOP_DIR", raising=False)
    expected_desktop = str(fake_home / "Work" / "DesktopSpace")

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="show desktop folder",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("list_dir", msg)
    assert "notes.txt" in result
    execute_mock.assert_awaited_once_with("list_dir", {"path": expected_desktop})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_updates_working_directory(agent_loop):
    execute_mock = AsyncMock(return_value="📄 README.md")
    agent_loop.tools.execute = execute_mock
    target_dir = agent_loop.workspace / "desktop" / "bot"
    target_dir.mkdir(parents=True, exist_ok=True)

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content=f"buka {target_dir}",
        metadata={},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("list_dir", msg)

    assert "README" in result
    assert msg.metadata.get("working_directory") == str(target_dir.resolve())
    assert msg.metadata.get("last_navigated_path") is None


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_keeps_working_directory_canonical_without_redundant_breadcrumb(
    agent_loop,
):
    execute_mock = AsyncMock(return_value="📄 README.md")
    agent_loop.tools.execute = execute_mock
    target_dir = agent_loop.workspace / "desktop" / "bot"
    target_dir.mkdir(parents=True, exist_ok=True)

    msg = InboundMessage(
        channel="cli",
        chat_id="direct-canonical-cwd",
        sender_id="user",
        content=f"buka {target_dir}",
        metadata={},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("list_dir", msg)
    session = agent_loop.sessions.get_or_create("cli:direct-canonical-cwd")

    assert "README" in result
    assert msg.metadata.get("working_directory") == str(target_dir.resolve())
    assert msg.metadata.get("last_navigated_path") is None
    assert session.metadata.get("working_directory") == str(target_dir.resolve())
    assert session.metadata.get("last_navigated_path") is None


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_resolves_relative_subfolder_from_last_context(agent_loop):
    execute_mock = AsyncMock(return_value="📄 CHANGELOG.md\n📁 kabot")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="tampilkan isi folder kabot",
        metadata={"last_tool_context": {"path": r"C:\Users\Arvy Kairi\Desktop\bot"}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("list_dir", msg)
    assert "CHANGELOG" in result
    execute_mock.assert_awaited_once_with("list_dir", {"path": r"C:\Users\Arvy Kairi\Desktop\bot\kabot"})

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
async def test_execute_required_tool_fallback_weather_explicit_new_location_beats_stale_last_tool_context(agent_loop):
    execute_mock = AsyncMock(return_value="Purwokerto: 24.9C, berkabut")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="suhu di purwokerto sekarang berapa",
        metadata={"last_tool_context": {"location": "Cilacap Utara"}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("weather", msg)

    assert result == "Purwokerto: 24.9C, berkabut"
    execute_mock.assert_awaited_once_with(
        "weather",
        {"location": "Purwokerto", "context_text": "suhu di purwokerto sekarang berapa"},
    )


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_weather_forecast_followup_uses_last_location_and_hour_window(
    agent_loop,
):
    execute_mock = AsyncMock(return_value="Cilacap forecast")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="prediksi 3-6 jam ke depan",
        metadata={"last_tool_context": {"tool": "weather", "location": "Cilacap"}},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("weather", msg)

    assert result == "Cilacap forecast"
    execute_mock.assert_awaited_once_with(
        "weather",
        {
            "location": "Cilacap",
            "context_text": "prediksi 3-6 jam ke depan",
            "mode": "hourly",
            "hours_ahead_start": 3,
            "hours_ahead_end": 6,
        },
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
async def test_execute_required_tool_fallback_web_search_compacts_conversational_live_news_query(agent_loop):
    execute_mock = AsyncMock(return_value="1. Reuters ...")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content=(
            "Adakah gejolak politik sekarang? Saya dengar ada konflik Iran vs US/Israel, "
            "tolong jawab seperti asisten yang paham berita terbaru."
        ),
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("web_search", msg)
    assert "Reuters" in result
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "web_search"
    assert "iran" in params["query"].lower()
    assert "israel" in params["query"].lower()
    assert "tolong jawab seperti asisten" not in params["query"].lower()
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
async def test_execute_required_tool_fallback_read_file_ignores_verbose_stale_prompt_on_low_information_followup(agent_loop):
    execute_mock = AsyncMock(return_value="file-content")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="lanjut",
        metadata={
            "required_tool_query": "Please provide the file path to read (example: config.json or C:\\path\\to\\file.json)."
        },
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("read_file", msg)
    assert result == i18n_t("filesystem.need_path", msg.content)
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
async def test_execute_required_tool_fallback_stock_keeps_resolved_query_when_raw_followup_has_no_stock_payload(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="kalau dirupiahkan dengan harga sekarang berapa",
        metadata={"required_tool_query": "saham apple berapa"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "stock"
    assert "apple" in params["symbol"].lower()
    assert "dirupiahkan" in params["symbol"].lower()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_short_conversion_followup_combines_previous_symbol_context(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="ubah jadi idr harganya",
        metadata={"required_tool_query": "msft"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once()
    tool_name, params = execute_mock.await_args.args
    assert tool_name == "stock"
    assert "msft" in params["symbol"].lower()
    assert "idr" in params["symbol"].lower()

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_short_followup_with_explicit_symbol_prefers_raw_text(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="ADRO mana",
        metadata={"required_tool_query": "cek harga saham bbri bbca bmri"},
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "ADRO.JK"})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_routes_tracking_requests_to_stock_analysis(agent_loop):
    execute_mock = AsyncMock(return_value="analysis-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="dalam 1 bulan terakhir gimana pergerakan saham bri nya",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "analysis-ok"
    if agent_loop.tools.has("stock_analysis"):
        execute_mock.assert_awaited_once_with("stock_analysis", {"symbol": "BBRI.JK", "days": "30"})
    else:
        execute_mock.assert_awaited_once_with("stock", {"symbol": "BBRI.JK"})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_analysis_serializes_days_as_string(agent_loop):
    execute_mock = AsyncMock(return_value="analysis-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="Buatkan 3 skenario trading AAPL: breakout, pullback, invalidation",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock_analysis", msg)

    assert result == "analysis-ok"
    execute_mock.assert_awaited_once_with("stock_analysis", {"symbol": "AAPL", "days": "30"})

@pytest.mark.asyncio
async def test_execute_required_tool_fallback_stock_routes_usd_idr_natural_query(agent_loop):
    execute_mock = AsyncMock(return_value="stock-ok")
    agent_loop.tools.execute = execute_mock

    msg = InboundMessage(
        channel="telegram",
        chat_id="8086",
        sender_id="user",
        content="gunakan yahoo finance harga 1 usd berapa rupiah",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("stock", msg)
    assert result == "stock-ok"
    execute_mock.assert_awaited_once_with("stock", {"symbol": "USDIDR=X"})

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


def test_extract_list_dir_path_supports_nested_special_directory_plus_subfolder(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))

    assert _extract_list_dir_path(
        "\u30c7\u30b9\u30af\u30c8\u30c3\u30d7\u306ebot\u30d5\u30a9\u30eb\u30c0\u306e\u4e2d\u3001\u6700\u521d\u306e5\u4ef6\u3060\u3051\u898b\u305b\u3066\u3002"
    ) == str(tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop/bot"))


def test_extract_list_dir_path_supports_special_directory_path_hint_without_folder_keyword(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))

    assert _extract_list_dir_path("ya pakai path desktop bot") == str(
        tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop/bot")
    )


def test_extract_list_dir_path_prefers_xdg_desktop_dir_when_set(monkeypatch):
    fake_home = tool_enforcement_module.Path("/home/arvy")
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: fake_home)
    monkeypatch.setenv("XDG_DESKTOP_DIR", "$HOME/Work/DesktopSpace")

    assert _extract_list_dir_path("open desktop folder") == str(
        fake_home / "Work" / "DesktopSpace"
    )


def test_extract_list_dir_path_prefers_user_dirs_config_for_downloads(monkeypatch, tmp_path):
    fake_home = tmp_path / "home"
    user_dirs = fake_home / ".config" / "user-dirs.dirs"
    user_dirs.parent.mkdir(parents=True, exist_ok=True)
    user_dirs.write_text('XDG_DOWNLOAD_DIR="$HOME/files/DownloadsCustom"\n', encoding="utf-8")
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: fake_home)
    monkeypatch.delenv("XDG_DOWNLOAD_DIR", raising=False)

    assert _extract_list_dir_path("show downloads folder") == str(
        fake_home / "files" / "DownloadsCustom"
    )


def test_extract_list_dir_path_path_hint_uses_xdg_desktop_dir(monkeypatch):
    fake_home = tool_enforcement_module.Path("/home/arvy")
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: fake_home)
    monkeypatch.setenv("XDG_DESKTOP_DIR", "$HOME/Work/DesktopSpace")

    assert _extract_list_dir_path("use path desktop bot") == str(
        fake_home / "Work" / "DesktopSpace" / "bot"
    )


def test_infer_action_required_tool_for_loop_prefers_list_dir_for_natural_path_hint(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))
    loop = SimpleNamespace(tools=SimpleNamespace(tool_names=["list_dir"]))

    assert infer_action_required_tool_for_loop(loop, "ya pakai path desktop bot") == (
        "list_dir",
        "ya pakai path desktop bot",
    )


def test_extract_message_delivery_path_uses_monkeypatched_special_directory_home(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))

    assert _extract_message_delivery_path("kirim desktop ke chat ini") == str(
        tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop")
    )


def test_extract_message_delivery_path_does_not_treat_delivery_verb_as_desktop_subfolder(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))

    assert _extract_message_delivery_path("kirim folder desktop ke chat ini") == str(
        tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop")
    )


def test_extract_list_dir_path_handles_open_relative_folder_with_trailing_slash(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))

    assert _extract_list_dir_path(
        r"buka bot\\",
        last_tool_context={"path": str(tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop"))},
    ) == str(tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop") / "bot")


def test_extract_read_file_path_prefers_filename_when_sentence_contains_folder_hint_with_delivery_tail():
    assert _extract_read_file_path(r"kirim file telegram_demo.md di folder bot\\ kesini") == "telegram_demo.md"


def test_extract_message_delivery_path_joins_relative_filename_with_folder_context_hint(monkeypatch):
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))

    assert _extract_message_delivery_path(
        r"kirim file telegram_demo.md di folder bot\\ kesini",
        last_tool_context={"path": str(tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop/bot"))},
    ) == str(tool_enforcement_module.Path("/Users/Arvy Kairi/Desktop/bot") / "telegram_demo.md")


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_passes_requested_limit(agent_loop, monkeypatch):
    execute_mock = AsyncMock(return_value="📁 bot\n📁 reference-repo")
    agent_loop.tools.execute = execute_mock
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))
    expected_desktop = str(tool_enforcement_module.Path("/Users/Arvy Kairi") / "Desktop")

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="cek file/folder di desktop isinya apa aja, 5 item pertama aja",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("list_dir", msg)
    assert "bot" in result
    execute_mock.assert_awaited_once_with("list_dir", {"path": expected_desktop, "limit": 5})


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_handles_normalized_special_dir_subfolder(
    agent_loop,
    monkeypatch,
):
    execute_mock = AsyncMock(return_value="CHANGELOG.md\ndocs\nkabot")
    agent_loop.tools.execute = execute_mock
    monkeypatch.setattr(tool_enforcement_module, "_filesystem_home_dir", lambda: tool_enforcement_module.Path("/Users/Arvy Kairi"))
    expected_bot = str(tool_enforcement_module.Path("/Users/Arvy Kairi") / "Desktop" / "bot")

    msg = InboundMessage(
        channel="cli",
        chat_id="direct",
        sender_id="user",
        content="bro, desktop?bot folder 3 item aja dong, jangan web ya",
        timestamp=datetime.now(),
    )

    result = await agent_loop._execute_required_tool_fallback("list_dir", msg)
    assert "CHANGELOG" in result
    execute_mock.assert_awaited_once_with("list_dir", {"path": expected_bot, "limit": 3})
