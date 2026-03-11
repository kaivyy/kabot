"""Split from tests/agent/test_tool_enforcement.py to keep test modules below 1000 lines.
Chunk 1: test_required_tool_for_query_detects_weather_and_reminder .. test_execute_required_tool_fallback_stock_maps_phrase_aliases_for_novice_company_names.
"""

import re
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from kabot.agent.fallback_i18n import t as i18n_t
from kabot.agent.loop import AgentLoop
from kabot.agent.loop_core import tool_enforcement as tool_enforcement_module
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_path,
    _extract_message_delivery_path,
    _extract_read_file_path,
    _query_has_tool_payload,
    infer_action_required_tool_for_loop,
    execute_required_tool_fallback,
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

def test_required_tool_for_query_detects_stock_from_explicit_tickers_without_stock_keyword(agent_loop):
    assert agent_loop._required_tool_for_query("bbri bbca bmri sekarang berapa") == "stock"
    assert agent_loop._required_tool_for_query("bbca.jk now") == "stock"
    assert agent_loop._required_tool_for_query("bank mandiri berapa sekarang") == "stock"
    assert agent_loop._required_tool_for_query("bank rakyat indonesia dan bank central asia") == "stock"
    assert agent_loop._required_tool_for_query("toyota sekarang berapa") == "stock"
    assert agent_loop._required_tool_for_query("トヨタ 株価 いくら") == "stock"
    assert agent_loop._required_tool_for_query("iya kamu bener") is None
    assert agent_loop._required_tool_for_query("umur kamu berapa sekarang") is None

def test_required_tool_for_query_detects_stock_tracking_and_fx_queries(agent_loop):
    assert agent_loop._required_tool_for_query("dalam 1 bulan terakhir gimana pergerakan saham bri nya") == "stock_analysis"
    assert agent_loop._required_tool_for_query("track apple stock movement 3 months") == "stock_analysis"
    assert agent_loop._required_tool_for_query("1 usd berapa rupiah sekarang") == "stock"
    assert agent_loop._required_tool_for_query("kurs usd ke idr hari ini") == "stock"
    assert agent_loop._required_tool_for_query("kalau dirupiahkan dengan harga sekarang berapa") is None
    assert (
        agent_loop._required_tool_for_query(
            "If Apple is around 260 dollars, roughly how much is that in Indonesian rupiah today?"
        )
        == "stock"
    )
    assert agent_loop._required_tool_for_query("cenderung turun atau naik?") is None

def test_required_tool_for_query_chat_mix_matrix(agent_loop):
    # End-to-end style routing expectations for common real-chat prompts.
    cases = [
        (
            "adakah gejolak politik sekarang? saya dengar ada perang iran vs us israel ya",
            "web_search",
        ),
        ("cek suhu purwokerto jawa tengah sekarang", "weather"),
        ("cek harga saham bbri bbca bmri adaro", "stock"),
        ("harga btc terbaru", "crypto"),
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
    assert agent_loop._required_tool_for_query("market cap bbca sekarang") == "stock"


def test_required_tool_for_query_does_not_route_general_knowledge_questions_to_stock(agent_loop):
    assert agent_loop._required_tool_for_query("JAM BERAPA") is None
    assert agent_loop._required_tool_for_query("jam berapa sekarang") is None
    assert agent_loop._required_tool_for_query("IQ MANUSIA BERAPA") is None
    assert agent_loop._required_tool_for_query("iq manusia berapa") is None
    assert agent_loop._required_tool_for_query("IQ MANUSIA RATA RATA BERAPA") is None
    assert agent_loop._required_tool_for_query("KALAU EQ MANUSIA BERAPA") is None


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
        == "stock_analysis"
    )
    assert (
        agent_loop._required_tool_for_query(
            "buatkan rencana entry exit aapl dengan support resistance dan stop loss"
        )
        == "stock_analysis"
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
    execute_mock = AsyncMock(return_value="📁 bot\n📁 openclaw")
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
    execute_mock.assert_awaited_once_with("stock_analysis", {"symbol": "BBRI.JK", "days": "30"})


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


@pytest.mark.asyncio
async def test_execute_required_tool_fallback_list_dir_passes_requested_limit(agent_loop, monkeypatch):
    execute_mock = AsyncMock(return_value="📁 bot\n📁 openclaw")
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
