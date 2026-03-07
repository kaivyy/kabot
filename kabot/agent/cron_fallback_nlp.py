"""NLP helpers for cron/reminder fallback parsing.

This module keeps parsing logic out of AgentLoop so reminder behavior is easier
to maintain and test in isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from kabot.agent.language.lexicon import (
    CRON_MANAGEMENT_OPS as LEXICON_CRON_MANAGEMENT_OPS,
)
from kabot.agent.language.lexicon import (
    CRON_MANAGEMENT_TERMS as LEXICON_CRON_MANAGEMENT_TERMS,
)
from kabot.agent.language.lexicon import (
    CRYPTO_TERMS as LEXICON_CRYPTO_TERMS,
)
from kabot.agent.language.lexicon import (
    REMINDER_TERMS as LEXICON_REMINDER_TERMS,
)
from kabot.agent.language.lexicon import (
    STOCK_TERMS as LEXICON_STOCK_TERMS,
)
from kabot.agent.language.lexicon import (
    WEATHER_TERMS as LEXICON_WEATHER_TERMS,
)
from kabot.agent.tools.stock import extract_stock_name_candidates, extract_stock_symbols

REMINDER_KEYWORDS = (
    "remind",
    "reminder",
    "schedule",
    "alarm",
    "timer",
    "wake me",
    "ingatkan",
    "pengingat",
    "jadwalkan",
    "bangunkan",
    "set sekarang",
    "jadwal",
    "cron",
    "shift",
    # Malay
    "peringatan",
    "jadual",
    "tetapkan",
    "minit",
    # Thai
    "เตือน",
    "การเตือน",
    "ตั้งเตือน",
    "นาฬิกา",
    # Chinese
    "提醒",
    "日程",
    "闹钟",
    "定时",
)

WEATHER_KEYWORDS = (
    "weather",
    "temperature",
    "forecast",
    "cuaca",
    "suhu",
    "temperatur",
    "prakiraan",
    # Malay
    "ramalan",
    # Thai
    "อากาศ",
    "อุณหภูมิ",
    "พยากรณ์",
    # Chinese
    "天气",
    "气温",
    "温度",
    "预报",
)

PROCESS_RAM_KEYWORDS = (
    # Direct RAM check - EN
    "ram usage", "memory usage", "check ram", "check memory",
    "how much ram", "what's using ram", "top memory", "top ram",
    "process memory", "process ram", "process list",
    "ram per app", "task manager",
    # Direct RAM check - ID/MS (Indonesian/Malay)
    "periksa ram", "cek ram", "lihat ram", "tampilkan ram",
    "penggunaan ram", "penggunaan memori",
    "ram per app", "ram per aplikasi", "ram per proses",
    "ram terbesar", "aplikasi boros", "aplikasi makan ram",
    "proses boros", "proses makan ram", "proses terbesar",
    "daftar proses", "top proses",
    "berapa ram", "ram berapa", "kapasitas ram", "kapasitas memori",
    "total ram", "total memori", "ram pc", "ram laptop", "ram komputer",
    # Multilingual
    "memoria", "uso de memoria", "uso de ram",
    "utilisation mémoire", "utilisation ram",
    "verwendung ram", "speichernutzung",
    "использование памяти", "использование озу",
    "uso de memória", "su dung ram", "su dung bo nho",
    "หน่วยความจำ", "การใช้แรม", "ใช้แรม",
    "内存", "内存使用", "内存占用", "进程",
    "메모리", "메모리 사용", "프로세스",
    "メモリ", "メモリ使用", "プロセス",
)

SYSTEM_INFO_KEYWORDS = (
    "spek", "spec", "specs", "spesifikasi", "specification",
    "hardware", "cpu", "gpu",
    "pc mu", "pc kamu", "your pc", "your computer",
    "komputer mu", "komputer kamu", "mesin mu", "mesin kamu",
    "detail pc", "cek pc", "check pc",
    "system info", "sysinfo",
    # --- Disk / Storage free-space queries (ID, EN, MS, TH, ZH) ---
    "ssd", "hdd", "storage", "penyimpanan", "disk",
    "space ssd", "space hdd", "sisa ssd", "sisa hdd",
    "space", "free space", "sisa ruang", "ruang disk", "ruang kosong",
    "kapasitas disk", "kapasitas ssd", "kapasitas hdd",
    "disk space", "disk usage", "penggunaan disk",
    "check disk", "cek disk", "cek storage", "cek ssd",
    "berapa sisa", "sisa storage",
    # Malay
    "storan", "ruang bebas", "penggunaan cakera",
    # Thai
    "พื้นที่ดิสก์", "พื้นที่ว่าง", "สตอเรจ", "ฮาร์ดดิสก์",
    # Chinese
    "硬盘", "存储", "磁盘空间", "剩余空间", "可用空间",
)

SERVER_MONITOR_KEYWORDS = (
    # English
    "monitor", "monitoring", "resource usage", "server status", "server health",
    "cpu usage", "ram usage", "memory usage", "cpu load", "resource check",
    "how much ram", "how much cpu", "how much memory",
    "system monitor", "server monitor", "pc monitor",
    "uptime", "server uptime",
    # Indonesian / Malay
    "monitor server", "monitoring server", "monitor pc", "pantau server",
    "penggunaan cpu", "penggunaan ram", "penggunaan memori",
    "cek resource", "cek server", "status server", "kondisi server",
    "berapa ram", "berapa cpu", "pemakaian ram", "pemakaian cpu",
    "beban server", "beban cpu", "beban ram",
    "periksa server", "monitor sistem", "pantau sistem",
    # Thai
    "ตรวจสอบเซิร์ฟเวอร์", "การใช้งาน CPU", "การใช้งาน RAM", "สถานะเซิร์ฟเวอร์",
    # Chinese
    "监控", "服务器监控", "服务器状态", "CPU使用率", "内存使用率", "系统监控",
    # Korean
    "서버 모니터링", "CPU 사용량", "RAM 사용량", "서버 상태",
    # Japanese
    "サーバー監視", "CPU使用率", "メモリ使用率", "サーバー状態",
)

CLEANUP_KEYWORDS = (
    "cleanup", "clean up", "bersihin", "bersihkan", "pembersihan",
    "free space", "freespace", "free disk",
    "hapus cache", "hapus temp", "clear cache", "clear temp",
    "disk cleanup", "disk clean",
    "recycle bin", "tempat sampah",
    "optimasi", "optimize", "optimise",
    "cleanup pc", "cleanup ssd", "cleanup hdd",
    "bersihin ssd", "bersihin hdd", "bersihin disk",
    "kosongkan", "free up",
    # Thai
    "ล้าง", "ล้างแคช", "เคลียร์แคช", "ทำความสะอาดดิสก์", "ลบไฟล์ชั่วคราว",
    # Chinese
    "清理", "清理缓存", "清除缓存", "清理磁盘", "磁盘清理", "释放空间",
)

# Avoid routing conflicts with system-info queries (e.g. "cek free space").
# Cleanup should require an explicit cleanup/action intent.
CLEANUP_ACTION_KEYWORDS = (
    "cleanup", "clean up", "bersihin", "bersihkan", "pembersihan",
    "hapus cache", "hapus temp", "clear cache", "clear temp",
    "disk cleanup", "disk clean",
    "recycle bin", "tempat sampah",
    "optimasi", "optimize", "optimise",
    "cleanup pc", "cleanup ssd", "cleanup hdd",
    "bersihin ssd", "bersihin hdd", "bersihin disk",
    "kosongkan", "free up",
    # Thai
    "ล้าง", "ล้างแคช", "เคลียร์แคช", "ทำความสะอาดดิสก์", "ลบไฟล์ชั่วคราว",
    # Chinese
    "清理", "清理缓存", "清除缓存", "清理磁盘", "磁盘清理", "释放空间",
)

SPEEDTEST_KEYWORDS = (
    "speedtest", "speed test", "cek speed", "cek koneksi",
    "cek internet", "tes internet", "tes speed", "tes koneksi",
    "berapa speed", "berapa kecepatan", "kecepatan internet",
    "internet speed", "connection speed", "network speed",
    "ping pc", "cek ping", "tes ping",
)

NEWS_KEYWORDS = (
    # English
    "news", "headline", "breaking news", "latest news", "current events",
    # Indonesian / Malay
    "berita", "kabar", "berita terbaru", "berita terkini", "kabar terbaru",
    # Simple multilingual anchors
    "noticias", "actualites", "nachrichten", "новости", "新闻", "ข่าว",
)

CHECK_UPDATE_KEYWORDS = (
    "check update",
    "cek update",
    "check for update",
    "check for updates",
    "cek versi terbaru",
    "versi terbaru kabot",
    "latest version",
    "is there an update",
    "ada update",
    "ada update kabot",
)

APPLY_UPDATE_KEYWORDS = (
    "update kabot",
    "upgrade kabot",
    "perbarui kabot",
    "pasang update kabot",
    "install update kabot",
    "update program kabot",
    "update bot kabot",
    "update server kabot",
)

CRON_MANAGEMENT_OPS = (
    "list",
    "lihat",
    "show",
    "hapus",
    "delete",
    "remove",
    "edit",
    "ubah",
    "update",
    # Malay
    "senarai",
    "padam",
    "kemas kini",
    # Thai
    "รายการ",
    "แสดง",
    "ลบ",
    "แก้ไข",
    "อัปเดต",
    # Chinese
    "列表",
    "查看",
    "显示",
    "删除",
    "移除",
    "编辑",
    "修改",
    "更新",
)
CRON_MANAGEMENT_TERMS = (
    "reminder",
    "pengingat",
    "jadwal",
    "cron",
    "shift",
    # Malay
    "peringatan",
    "jadual",
    # Thai
    "เตือน",
    "ตาราง",
    # Chinese
    "提醒",
    "日程",
    "计划",
)


# Use centralized multilingual lexicon across router/quality/fallback modules.
REMINDER_KEYWORDS = LEXICON_REMINDER_TERMS
WEATHER_KEYWORDS = LEXICON_WEATHER_TERMS
CRON_MANAGEMENT_OPS = LEXICON_CRON_MANAGEMENT_OPS
CRON_MANAGEMENT_TERMS = LEXICON_CRON_MANAGEMENT_TERMS
STOCK_KEYWORDS = LEXICON_STOCK_TERMS
CRYPTO_KEYWORDS = LEXICON_CRYPTO_TERMS


@dataclass(frozen=True)
class ToolIntentScore:
    """Scored tool-intent candidate for deterministic fallback routing."""

    tool: str
    score: float
    reason: str


_INTENT_MIN_SCORE = 0.55
_INTENT_STRONG_SCORE = 0.85
_INTENT_AMBIGUITY_DELTA = 0.15

_LIVE_QUERY_MARKERS = (
    "latest",
    "breaking",
    "today",
    "now",
    "current",
    "headline",
    "headlines",
    "update",
    "terbaru",
    "terkini",
    "sekarang",
    "hari ini",
)
_RESEARCH_VERB_MARKERS = (
    "search",
    "find",
    "look up",
    "lookup",
    "cari",
    "carikan",
    "telusuri",
    "cek",
    "check",
)
_UPDATE_CHECK_VERBS = (
    "check",
    "cek",
    "lihat",
    "show",
    "is there",
    "ada",
)
_UPDATE_CONTEXT_MARKERS = (
    "update",
    "upgrade",
    "versi",
    "version",
    "pembaruan",
    "perbarui",
    "latest version",
)
_UPDATE_TARGET_MARKERS = (
    "kabot",
    "bot",
    "agent",
    "program",
    "app",
    "aplikasi",
    "server",
)
_UPDATE_APPLY_INTENT_MARKERS = (
    "upgrade",
    "install",
    "pasang",
    "perbarui",
)
_WEATHER_WIND_MARKERS = (
    "angin",
    "berangin",
    "wind",
    "windy",
    "windspeed",
    "wind speed",
    "wind direction",
    "arah angin",
    "kecepatan angin",
)
_GEO_NEWS_TOPIC_MARKERS = (
    "war",
    "perang",
    "conflict",
    "israel",
    "iran",
    "gaza",
    "ukraine",
    "russia",
    "usa",
    "amerika",
)
_GEO_NEWS_STRONG_TOPIC_MARKERS = (
    "war",
    "perang",
    "conflict",
    "israel",
    "iran",
    "gaza",
    "ukraine",
    "russia",
)
_REMINDER_TIME_RE = re.compile(
    r"(?i)\b\d+\s*(menit|jam|detik|hari|min(?:ute)?s?|hour(?:s)?|sec(?:ond)?s?|day(?:s)?)\b"
)
_STOCK_TOKEN_RE = re.compile(r"\b([A-Za-z]{1,10}(?:\.[A-Za-z]{1,4})?)\b")
_STOCK_EXPLICIT_SUFFIX_RE = re.compile(r"^[A-Z]{1,8}\.[A-Z]{1,4}$")
_CRYPTO_SYMBOL_MARKERS = (
    "btc",
    "bitcoin",
    "eth",
    "ethereum",
    "sol",
    "solana",
    "doge",
    "xrp",
    "bnb",
    "usdt",
)
_KNOWN_IDX_SYMBOLS = {
    "BBCA",
    "BBRI",
    "BMRI",
    "BBNI",
    "TLKM",
    "ASII",
    "GOTO",
    "ANTM",
    "UNVR",
    "INDF",
    "ICBP",
    "ADRO",
    "MDKA",
    "PTBA",
    "ACES",
    "SMGR",
    "EXCL",
    "ISAT",
    "KLBF",
    "SIDO",
    "CPIN",
    "JPFA",
    "AMRT",
    "MAPI",
    "SRTG",
    "TOWR",
}
_KNOWN_GLOBAL_SYMBOLS = {
    "AAPL",
    "MSFT",
    "TSLA",
    "NVDA",
    "META",
    "GOOG",
    "AMZN",
    "NFLX",
}
_STOCK_TOKEN_STOPWORDS = {
    "IYA",
    "YA",
    "KAMU",
    "SAYA",
    "AKU",
    "YANG",
    "DAN",
    "ATAU",
    "KALAU",
    "SEKARANG",
    "TODAY",
    "NOW",
    "BEST",
    "TOP",
    "LIST",
    "DAFTAR",
    "BANK",
    "MARKET",
    "STOCK",
    "SAHAM",
    "TICKER",
    "PRICE",
    "HARGA",
}
_RAM_CAPACITY_MARKERS = (
    "kapasitas",
    "total ram",
    "total memori",
    "ram terpasang",
    "installed ram",
    "memory capacity",
    "ram capacity",
    "ram berapa",
    "berapa ram",
    "spec",
    "spek",
    "spesifikasi",
)
_RAM_USAGE_MARKERS = (
    "usage",
    "penggunaan",
    "dipakai",
    "pemakaian",
    "per proses",
    "per process",
    "top",
    "boros",
    "makan ram",
    "process",
    "proses",
)
_DISK_SPACE_MARKERS = (
    "free space",
    "disk space",
    "sisa ruang",
    "ruang kosong",
    "sisa storage",
    "storage",
    "disk usage",
)
_STOCK_VALUE_QUERY_MARKERS = (
    "price",
    "harga",
    "quote",
    "berapa",
    "how much",
    # Multilingual value-query anchors
    "berapa harganya",
    "ราคา",
    "いくら",
    "株価",
    "价格",
    "股价",
    "가격",
    "주가",
)
_STOCK_TRACKING_MARKERS = (
    "track",
    "tracking",
    "trend",
    "movement",
    "history",
    "historical",
    "chart",
    "grafik",
    "pergerakan",
    "riwayat",
    "naik turun",
    "kinerja",
    "performance",
    "bulan terakhir",
    "hari terakhir",
    "minggu terakhir",
    "month",
    "months",
    "week",
    "weeks",
    "1m",
    "3m",
    "6m",
    "1y",
)
_FX_RATE_MARKERS = (
    "kurs",
    "exchange rate",
    "nilai tukar",
    "convert",
    "conversion",
    "konversi",
    "dirupiahkan",
    "rupiahkan",
    "usd",
    "idr",
    "rupiah",
    "dollar",
)
_FX_PAIR_MARKERS = (
    "usd idr",
    "usd/idr",
    "usd to idr",
    "usd ke idr",
    "usd ke rupiah",
    "dollar ke rupiah",
    "usdidr",
)
_FX_CONVERSION_AMOUNT_RE = re.compile(
    r"(?i)\b(?:around|about|roughly|sekitar|kurang lebih|kira-kira)?\s*(\d+(?:[.,]\d+)?)\s*(usd|dollar|dollars)\b"
)
_PERSONAL_CHAT_MARKERS = (
    "umur",
    "age",
    "old",
    "how old",
    "siapa kamu",
    "who are you",
    "apa kabar",
    "how are you",
)
_EMAIL_WORKFLOW_MARKERS = (
    "email",
    "gmail",
    "inbox",
    "draft",
    "subject",
    "recipient",
    "kirim email",
    "send email",
    "save draft",
    "reply email",
)
_PRODUCTIVITY_DOC_MARKERS = (
    "excel",
    "spreadsheet",
    "google sheet",
    "google sheets",
    "xlsx",
    "csv",
    "workbook",
)
_READ_FILE_ACTION_MARKERS = (
    "read file",
    "baca file",
    "open file",
    "buka file",
    "lihat file",
    "show file",
    "display file",
    "print file",
    "cat file",
    "cat ",
    "read config",
    "baca config",
)
_READ_FILE_SUBJECT_MARKERS = (
    "file",
    "berkas",
    "config",
    "configuration",
    "settings",
    "setting",
    "path",
    "folder",
    "direktori",
)
_FILELIKE_QUERY_RE = re.compile(
    r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml)\b",
    re.IGNORECASE,
)
_PATHLIKE_QUERY_RE = re.compile(r"([a-zA-Z]:\\|\\\\|/[\w\-./]+|[\w\-./]+\\[\w\-./]+)")
_META_FEEDBACK_MARKERS = (
    "kenapa jawab",
    "kenapa balas",
    "jawaban",
    "jawabannya",
    "balasannya",
    "why answer",
    "why did you answer",
    "response",
    "respon",
    "gitu",
    "begitu",
)
_META_TOPIC_MARKERS = (
    "bahas",
    "tentang",
    "soal",
    "about",
    "topic",
    "topik",
)
_NON_ACTION_MARKERS = (
    "stop",
    "hentikan",
    "berhenti",
    "jangan",
    "bukan",
    "dont",
    "don't",
    "do not",
    "not now",
    "cancel",
    "batalkan",
    "ga usah",
    "gak usah",
    "nggak usah",
    "tidak usah",
    "no need",
)


def _normalize_query(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _tokenize_latin_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _is_edit_distance_leq_one(left: str, right: str) -> bool:
    """Fast bounded Levenshtein check (distance <= 1)."""
    if left == right:
        return True
    len_left = len(left)
    len_right = len(right)
    if abs(len_left - len_right) > 1:
        return False
    if len_left == len_right:
        mismatches = 0
        for idx in range(len_left):
            if left[idx] != right[idx]:
                mismatches += 1
                if mismatches > 1:
                    return False
        return True
    if len_left > len_right:
        left, right = right, left
        len_left, len_right = len_right, len_left
    # now right is longer by exactly 1 char
    i = 0
    j = 0
    skipped = False
    while i < len_left and j < len_right:
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        if skipped:
            return False
        skipped = True
        j += 1
    return True


def _contains_any(text: str, terms: Iterable[str], *, fuzzy_latin: bool = False) -> bool:
    if any(term in text for term in terms):
        return True
    if not fuzzy_latin:
        return False
    tokens = _tokenize_latin_words(text)
    if not tokens:
        return False
    for raw_term in terms:
        term = _normalize_query(raw_term)
        if not term:
            continue
        if " " in term:
            parts = [part for part in term.split(" ") if part]
            if len(parts) < 2:
                continue
            latin_parts = [part for part in parts if re.fullmatch(r"[a-z0-9]+", part)]
            if len(latin_parts) != len(parts):
                continue
            matched_parts = 0
            for part in parts:
                if len(part) < 4:
                    continue
                if any(len(token) >= 4 and _is_edit_distance_leq_one(token, part) for token in tokens):
                    matched_parts += 1
            if matched_parts >= max(2, len(parts)):
                return True
            continue
        # Keep fuzzy matching conservative to reduce false positives.
        if len(term) < 5 or not re.fullmatch(r"[a-z0-9]+", term):
            continue
        for token in tokens:
            if len(token) < 4:
                continue
            if _is_edit_distance_leq_one(token, term):
                return True
    return False


def _extract_stock_symbol_candidates(question: str) -> list[str]:
    # Reuse stock-tool parser so deterministic router and stock tool stay aligned.
    return extract_stock_symbols(question or "")


def _extract_stock_name_candidates(question: str) -> list[str]:
    # Reuse stock-tool novice-name parser for consistent cross-module behavior.
    return extract_stock_name_candidates(question or "")


def score_required_tool_intents(
    question: str,
    *,
    has_weather_tool: bool,
    has_cron_tool: bool,
    has_system_info_tool: bool = False,
    has_cleanup_tool: bool = False,
    has_speedtest_tool: bool = False,
    has_process_memory_tool: bool = False,
    has_stock_tool: bool = False,
    has_stock_analysis_tool: bool = False,
    has_crypto_tool: bool = False,
    has_server_monitor_tool: bool = False,
    has_web_search_tool: bool = False,
    has_read_file_tool: bool = False,
    has_check_update_tool: bool = False,
    has_system_update_tool: bool = False,
) -> list[ToolIntentScore]:
    """
    Score tool intents using mixed structural signals + multilingual lexicon.

    This keeps deterministic fallback robust while reducing rigid keyword-only behavior.
    """
    text = str(question or "").strip()
    q_lower = _normalize_query(text)
    if not q_lower:
        return []

    available = {
        "weather": has_weather_tool,
        "cron": has_cron_tool,
        "get_system_info": has_system_info_tool,
        "cleanup_system": has_cleanup_tool,
        "speedtest": has_speedtest_tool,
        "get_process_memory": has_process_memory_tool,
        "stock": has_stock_tool,
        "stock_analysis": has_stock_analysis_tool,
        "crypto": has_crypto_tool,
        "server_monitor": has_server_monitor_tool,
        "web_search": has_web_search_tool,
        "read_file": has_read_file_tool,
        "check_update": has_check_update_tool,
        "system_update": has_system_update_tool,
    }
    scores: dict[str, float] = {}
    reasons: dict[str, str] = {}

    def add(tool: str, points: float, reason: str) -> None:
        if not available.get(tool, False):
            return
        if points <= 0:
            return
        current = scores.get(tool, 0.0)
        next_score = min(1.0, current + float(points))
        scores[tool] = next_score
        reasons.setdefault(tool, reason)

    has_non_action_marker = _contains_any(q_lower, _NON_ACTION_MARKERS, fuzzy_latin=True)
    has_meta_feedback_marker = _contains_any(q_lower, _META_FEEDBACK_MARKERS, fuzzy_latin=True)
    has_meta_topic_marker = _contains_any(q_lower, _META_TOPIC_MARKERS, fuzzy_latin=True)

    def _is_non_action_meta_domain_turn(
        *,
        has_domain_marker: bool,
        has_structural_payload: bool = False,
    ) -> bool:
        """Suppress lexicon-only domain routing for meta/negation chat turns."""
        if not has_domain_marker:
            return False
        if has_structural_payload:
            return False
        if not has_non_action_marker:
            return False
        return has_meta_feedback_marker or has_meta_topic_marker

    # 1) High-priority deterministic updates.
    if _contains_any(q_lower, CHECK_UPDATE_KEYWORDS, fuzzy_latin=True):
        add("check_update", 0.98, "explicit-check-update")
    if _contains_any(q_lower, APPLY_UPDATE_KEYWORDS, fuzzy_latin=True):
        add("system_update", 0.98, "explicit-apply-update")
    has_update_context = _contains_any(q_lower, _UPDATE_CONTEXT_MARKERS, fuzzy_latin=True)
    has_update_check_intent = has_update_context and _contains_any(
        q_lower, _UPDATE_CHECK_VERBS, fuzzy_latin=True
    )
    has_update_apply_intent = has_update_context and _contains_any(
        q_lower, _UPDATE_APPLY_INTENT_MARKERS, fuzzy_latin=True
    )
    if has_update_check_intent:
        add("check_update", 1.0, "check-update-verb")
    if has_update_apply_intent and not has_update_check_intent:
        add("system_update", 0.08, "apply-update-verb")

    # 2) Cron/reminder intent (management + creation).
    if _contains_any(q_lower, CRON_MANAGEMENT_OPS, fuzzy_latin=True) and _contains_any(
        q_lower, CRON_MANAGEMENT_TERMS, fuzzy_latin=True
    ):
        add("cron", 0.96, "cron-management")
    if _contains_any(q_lower, REMINDER_KEYWORDS, fuzzy_latin=True):
        add("cron", 0.72, "reminder-lexicon")
    if _REMINDER_TIME_RE.search(q_lower) and _contains_any(
        q_lower, ("ingat", "remind", "alarm", "timer", "schedule", "jadwal")
    ):
        add("cron", 0.22, "time-plus-reminder-structure")
    if _REMINDER_TIME_RE.search(q_lower):
        looks_like_question = ("?" in text) or bool(
            re.match(
                r"(?i)^(what|why|how|when|where|who|berapa|kenapa|kapan|gimana|bagaimana|siapa|mana)\b",
                q_lower,
            )
        )
        has_other_domain_marker = any(
            (
                _contains_any(q_lower, WEATHER_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, STOCK_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SERVER_MONITOR_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, NEWS_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, CHECK_UPDATE_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, APPLY_UPDATE_KEYWORDS, fuzzy_latin=True),
            )
        )
        if not looks_like_question and not has_other_domain_marker:
            add("cron", 0.58, "time-action-structure")

    # 3) Weather.
    has_weather_marker = _contains_any(q_lower, WEATHER_KEYWORDS, fuzzy_latin=True) or _contains_any(
        q_lower,
        _WEATHER_WIND_MARKERS,
        fuzzy_latin=True,
    )
    location_candidate = extract_weather_location(text)
    location_candidate_lower = _normalize_query(location_candidate or "")
    location_looks_meta = _contains_any(
        location_candidate_lower,
        (*_META_TOPIC_MARKERS, *_NON_ACTION_MARKERS),
        fuzzy_latin=True,
    )
    has_weather_structural_payload = bool(location_candidate) and not location_looks_meta
    if has_weather_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=has_weather_structural_payload,
    ):
        add("weather", 0.64, "weather-lexicon")
    if has_weather_marker and has_weather_structural_payload:
        add("weather", 0.24, "weather-location")
    if has_weather_marker and _contains_any(q_lower, ("today", "hari ini", "now", "sekarang")):
        add("weather", 0.08, "weather-live-time")
    if (
        has_weather_marker
        and has_weather_structural_payload
        and has_update_context
        and not _contains_any(q_lower, _UPDATE_TARGET_MARKERS, fuzzy_latin=True)
    ):
        scores.pop("check_update", None)
        scores.pop("system_update", None)
        reasons.pop("check_update", None)
        reasons.pop("system_update", None)

    # 4) System/process monitoring.
    has_server_monitor_marker = _contains_any(q_lower, SERVER_MONITOR_KEYWORDS, fuzzy_latin=True)
    if has_server_monitor_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("server_monitor", 0.82, "server-monitor-lexicon")
    has_process_ram_marker = _contains_any(q_lower, PROCESS_RAM_KEYWORDS, fuzzy_latin=True)
    if has_process_ram_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("get_process_memory", 0.76, "process-memory-lexicon")
    has_ram_capacity_marker = _contains_any(q_lower, _RAM_CAPACITY_MARKERS, fuzzy_latin=True)
    if has_ram_capacity_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("get_system_info", 0.82, "ram-capacity-structure")
    has_system_info_marker = _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True) or _contains_any(
        q_lower, _DISK_SPACE_MARKERS, fuzzy_latin=True
    )
    if has_system_info_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("get_system_info", 0.66, "system-info-lexicon")
    if _contains_any(q_lower, _RAM_USAGE_MARKERS, fuzzy_latin=True) and _contains_any(
        q_lower, ("ram", "memory", "memori"), fuzzy_latin=True
    ):
        add("get_process_memory", 0.16, "ram-usage-structure")

    # 4b) File-reading requests.
    has_read_file_action = _contains_any(q_lower, _READ_FILE_ACTION_MARKERS, fuzzy_latin=True)
    has_read_file_subject = _contains_any(q_lower, _READ_FILE_SUBJECT_MARKERS, fuzzy_latin=True)
    has_file_payload = bool(_FILELIKE_QUERY_RE.search(text) or _PATHLIKE_QUERY_RE.search(text))
    if has_read_file_action and has_file_payload:
        add("read_file", 0.93, "read-file-action-plus-path")
    elif has_read_file_action and has_read_file_subject:
        add("read_file", 0.74, "read-file-action-plus-subject")
    elif has_file_payload and has_read_file_subject:
        add("read_file", 0.58, "read-file-subject-plus-path")

    # 5) Stock/crypto with structural entity detection.
    has_geo_news_strong_marker = _contains_any(
        q_lower, _GEO_NEWS_STRONG_TOPIC_MARKERS, fuzzy_latin=True
    )
    has_email_workflow_marker = _contains_any(q_lower, _EMAIL_WORKFLOW_MARKERS, fuzzy_latin=True)
    has_productivity_doc_marker = _contains_any(q_lower, _PRODUCTIVITY_DOC_MARKERS, fuzzy_latin=True)
    stock_symbols = _extract_stock_symbol_candidates(text)
    crypto_symbol_set = {str(token).lower() for token in _CRYPTO_SYMBOL_MARKERS}
    stock_symbols_non_crypto = [
        symbol
        for symbol in stock_symbols
        if str(symbol).strip().lower() not in crypto_symbol_set
    ]
    stock_name_candidates = _extract_stock_name_candidates(text)
    has_stock_marker = (
        _contains_any(q_lower, STOCK_KEYWORDS, fuzzy_latin=True)
        and not has_email_workflow_marker
        and not has_productivity_doc_marker
    )
    has_stock_tracking_marker = _contains_any(q_lower, _STOCK_TRACKING_MARKERS, fuzzy_latin=True)
    has_fx_pair_marker = (
        _contains_any(q_lower, _FX_PAIR_MARKERS, fuzzy_latin=True)
        or bool(re.search(r"\busd\s*(?:/|to|ke|-)?\s*(?:idr|rupiah)\b", q_lower))
        or bool(re.search(r"\b(?:idr|rupiah)\s*(?:/|to|ke|-)?\s*usd\b", q_lower))
    )
    has_fx_rate_marker = _contains_any(q_lower, _FX_RATE_MARKERS, fuzzy_latin=True)
    has_fx_conversion_amount = bool(_FX_CONVERSION_AMOUNT_RE.search(text))
    stock_has_structural_payload = bool(stock_symbols_non_crypto)
    if has_fx_pair_marker and (has_fx_rate_marker or _contains_any(q_lower, _STOCK_VALUE_QUERY_MARKERS, fuzzy_latin=True)):
        add("stock", 0.94, "fx-rate-query")
        stock_has_structural_payload = True
    if len(stock_symbols_non_crypto) >= 2:
        add("stock", 0.88, "multi-stock-symbols")
    elif len(stock_symbols_non_crypto) == 1:
        symbol = stock_symbols_non_crypto[0]
        if "." in symbol or has_stock_marker:
            add("stock", 0.8, "explicit-stock-symbol")
        else:
            add("stock", 0.64, "known-stock-symbol")
    if has_stock_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=stock_has_structural_payload,
    ):
        add("stock", 0.32 if has_stock_tracking_marker else 0.56, "stock-lexicon")
    if stock_name_candidates and not stock_symbols_non_crypto:
        has_value_query_marker = _contains_any(q_lower, _STOCK_VALUE_QUERY_MARKERS, fuzzy_latin=True)
        stock_has_structural_payload = bool(stock_has_structural_payload or has_value_query_marker)
        has_personal_chat_marker = _contains_any(q_lower, _PERSONAL_CHAT_MARKERS, fuzzy_latin=True)
        is_currency_conversion_without_explicit_market = (
            has_fx_rate_marker
            and not has_fx_pair_marker
            and not has_stock_marker
            and not stock_symbols_non_crypto
        )
        has_conflicting_domain = any(
            (
                has_weather_marker,
                has_geo_news_strong_marker,
                _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, _CRYPTO_SYMBOL_MARKERS),
                _contains_any(q_lower, REMINDER_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SERVER_MONITOR_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, CLEANUP_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True),
                _contains_any(q_lower, NEWS_KEYWORDS, fuzzy_latin=True),
                has_email_workflow_marker,
                has_productivity_doc_marker,
            )
        )
        if (
            has_value_query_marker
            and not has_personal_chat_marker
            and not has_conflicting_domain
            and not is_currency_conversion_without_explicit_market
        ):
            add("stock", 0.62, "stock-company-name-value-query")
        if (
            has_fx_rate_marker
            and (has_fx_conversion_amount or has_value_query_marker)
            and not has_personal_chat_marker
            and not has_conflicting_domain
        ):
            add("stock", 0.9, "stock-company-fx-conversion")

    stock_analysis_has_payload = bool(
        stock_symbols_non_crypto
        or stock_name_candidates
        or has_stock_marker
        or has_fx_pair_marker
    )
    if has_stock_tracking_marker and stock_analysis_has_payload and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=stock_analysis_has_payload,
    ):
        add("stock_analysis", 0.92, "stock-tracking-analysis")

    has_crypto_marker = _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True)
    has_crypto_symbol = _contains_any(q_lower, _CRYPTO_SYMBOL_MARKERS)
    if has_crypto_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=has_crypto_symbol,
    ):
        add("crypto", 0.66, "crypto-lexicon")
    if has_crypto_symbol:
        add("crypto", 0.86, "crypto-symbol-strong")

    # 6) Search/news intent with structural live-query hints.
    has_news_marker = _contains_any(q_lower, NEWS_KEYWORDS, fuzzy_latin=True)
    has_live_marker = _contains_any(q_lower, _LIVE_QUERY_MARKERS, fuzzy_latin=True)
    has_research_verb = _contains_any(q_lower, _RESEARCH_VERB_MARKERS, fuzzy_latin=True)
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", q_lower))
    has_local_ops_marker = any(
        (
            _contains_any(q_lower, REMINDER_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, WEATHER_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, PROCESS_RAM_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, SYSTEM_INFO_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, CLEANUP_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, STOCK_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, CRYPTO_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, _EMAIL_WORKFLOW_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _PRODUCTIVITY_DOC_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _READ_FILE_ACTION_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, _READ_FILE_SUBJECT_MARKERS, fuzzy_latin=True),
            _contains_any(q_lower, CHECK_UPDATE_KEYWORDS, fuzzy_latin=True),
            _contains_any(q_lower, APPLY_UPDATE_KEYWORDS, fuzzy_latin=True),
        )
    )
    has_meta_feedback_marker = _contains_any(q_lower, _META_FEEDBACK_MARKERS, fuzzy_latin=True)
    has_news_structural_payload = has_research_verb or has_live_marker or has_year or has_geo_news_strong_marker
    if has_news_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=has_news_structural_payload,
    ):
        if has_meta_feedback_marker and not (has_geo_news_strong_marker or has_year):
            add("web_search", 0.4, "news-meta-chat-soft")
        elif has_research_verb or has_live_marker or has_year or has_geo_news_strong_marker:
            add("web_search", 0.74, "news-lexicon")
        else:
            add("web_search", 0.45, "news-soft")
    if has_geo_news_strong_marker and (has_live_marker or has_research_verb or ("?" in text)):
        add("web_search", 0.7, "geo-news-topic")
    if has_live_marker and (has_research_verb or has_year) and not has_local_ops_marker:
        add("web_search", 0.62, "live-query-structure")
    if has_year and _contains_any(q_lower, _GEO_NEWS_TOPIC_MARKERS):
        add("web_search", 0.2, "dated-geo-topic")

    # 7) Speedtest / cleanup.
    has_speedtest_marker = _contains_any(q_lower, SPEEDTEST_KEYWORDS, fuzzy_latin=True)
    if has_speedtest_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("speedtest", 0.8, "speedtest-lexicon")
    has_cleanup_marker = _contains_any(q_lower, CLEANUP_KEYWORDS, fuzzy_latin=True)
    has_cleanup_action_marker = _contains_any(q_lower, CLEANUP_ACTION_KEYWORDS, fuzzy_latin=True)
    if (
        has_cleanup_marker
        and has_cleanup_action_marker
        and not _is_non_action_meta_domain_turn(has_domain_marker=True, has_structural_payload=False)
    ):
        add("cleanup_system", 0.86, "cleanup-action")
    elif has_cleanup_marker and not _is_non_action_meta_domain_turn(
        has_domain_marker=True,
        has_structural_payload=False,
    ):
        add("cleanup_system", 0.45, "cleanup-soft")

    ranked = sorted(
        (ToolIntentScore(tool=tool, score=score, reason=reasons.get(tool, "")) for tool, score in scores.items()),
        key=lambda item: item.score,
        reverse=True,
    )
    return ranked


def required_tool_for_query(
    question: str,
    has_weather_tool: bool,
    has_cron_tool: bool,
    has_system_info_tool: bool = False,
    has_cleanup_tool: bool = False,
    has_speedtest_tool: bool = False,
    has_process_memory_tool: bool = False,
    has_stock_tool: bool = False,
    has_stock_analysis_tool: bool = False,
    has_crypto_tool: bool = False,
    has_server_monitor_tool: bool = False,
    has_web_search_tool: bool = False,
    has_read_file_tool: bool = False,
    has_check_update_tool: bool = False,
    has_system_update_tool: bool = False,
) -> str | None:
    """Return deterministic required-tool routing with intent confidence gating."""
    q_lower = _normalize_query(question)
    if (
        has_system_info_tool
        and _contains_any(q_lower, _RAM_CAPACITY_MARKERS)
        and not _contains_any(q_lower, _RAM_USAGE_MARKERS)
    ):
        return "get_system_info"

    ranked = score_required_tool_intents(
        question,
        has_weather_tool=has_weather_tool,
        has_cron_tool=has_cron_tool,
        has_system_info_tool=has_system_info_tool,
        has_cleanup_tool=has_cleanup_tool,
        has_speedtest_tool=has_speedtest_tool,
        has_process_memory_tool=has_process_memory_tool,
        has_stock_tool=has_stock_tool,
        has_stock_analysis_tool=has_stock_analysis_tool,
        has_crypto_tool=has_crypto_tool,
        has_server_monitor_tool=has_server_monitor_tool,
        has_web_search_tool=has_web_search_tool,
        has_read_file_tool=has_read_file_tool,
        has_check_update_tool=has_check_update_tool,
        has_system_update_tool=has_system_update_tool,
    )
    if not ranked:
        return None

    best = ranked[0]
    if best.score < _INTENT_MIN_SCORE:
        return None

    # Tracking/history queries should favor analysis over quote-only stock tool.
    if best.tool == "stock":
        stock_analysis_candidate = next((item for item in ranked if item.tool == "stock_analysis"), None)
        if (
            stock_analysis_candidate
            and stock_analysis_candidate.score >= 0.8
            and _contains_any(q_lower, _STOCK_TRACKING_MARKERS, fuzzy_latin=True)
        ):
            return "stock_analysis"

    if len(ranked) > 1:
        second = ranked[1]
        if (
            best.score < _INTENT_STRONG_SCORE
            and (best.score - second.score) < _INTENT_AMBIGUITY_DELTA
        ):
            return None

    return best.tool


def extract_weather_location(question: str) -> str | None:
    """Extract probable weather location from user query."""

    def _strip_weather_terms(value: str) -> str:
        cleaned = str(value or "")
        weather_terms = tuple(sorted(set((*WEATHER_KEYWORDS, *_WEATHER_WIND_MARKERS)), key=len, reverse=True))
        for term in weather_terms:
            marker = str(term or "").strip()
            if not marker:
                continue
            if re.fullmatch(r"[a-z0-9 ]+", marker):
                cleaned = re.sub(rf"(?i)\b{re.escape(marker)}\b", " ", cleaned)
            else:
                cleaned = cleaned.replace(marker, " ")
        return cleaned

    def _format_location(value: str) -> str:
        out_parts: list[str] = []
        for part in str(value or "").split():
            if re.fullmatch(r"[a-z][a-z\-']*", part):
                out_parts.append(part.capitalize())
            else:
                out_parts.append(part)
        return " ".join(out_parts).strip()

    def _strip_conversational_prefix(value: str) -> str:
        cleaned = value
        prefix_pattern = (
            r"(?i)^(?:"
            r"ya|iya|ok|oke|sip|"
            r"tolong|please|coba|cek|check|semak|"
            r"gimana|bagaimana|kenapa|kok|kalau|kalo|"
            r"bisakah|bisa|could|can|why|what(?:'s| is)|"
            r"dong|deh|nih"
            r")\b[\s,.:;-]*"
        )
        while True:
            updated = re.sub(prefix_pattern, "", cleaned).strip()
            if updated == cleaned:
                break
            cleaned = updated
        return cleaned

    def _normalize_location_candidate(value: str) -> str:
        cleaned = _strip_conversational_prefix(value)
        cleaned = re.split(
            r"(?i)[?!\n]|(?:\s+-\s+)|\b(?:kan|karena|soalnya|but|tapi|however)\b",
            cleaned,
            maxsplit=1,
        )[0]
        cleaned = re.sub(
            r"(?i)\b(?:right now|hari ini|today|saat ini|sekarang|now|right|berapa|how much|what(?:'s| is)|derajat|degree|degrees|celsius|fahrenheit)\b",
            " ",
            cleaned,
        )
        cleaned = _strip_weather_terms(cleaned)
        multilingual_fillers = (
            "天気",
            "天气",
            "อากาศ",
            "の",
            "どうですか",
            "どう",
            "今日",
            "いま",
            "今",
            "今天",
            "现在",
            "怎麼樣",
            "怎么样",
            "怎样",
            "วันนี้",
            "ตอนนี้",
            "เป็นยังไง",
            "ยังไง",
            "？",
        )
        for marker in multilingual_fillers:
            cleaned = cleaned.replace(marker, " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")
        cleaned = re.sub(
            r"(?i)\b(?:kota|city|kabupaten|regency|district|county|municipality|province|provinsi)\b$",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;")

        edge_fillers = {
            "ya", "iya", "ok", "oke", "sip", "tolong", "please", "coba", "cek", "check",
            "semak", "gimana", "bagaimana", "kenapa", "kok", "kalau", "kalo", "bisa", "bisakah",
            "can", "could", "why", "dong", "deh", "nih", "kan", "udah", "sudah", "pasti",
            "itu", "yang", "di", "in", "apa", "ga", "gak", "ngga", "nggak", "enggak", "tidak",
            "天", "气", "風", "风",
        }
        tokens = [tok for tok in cleaned.split() if tok]
        while tokens and tokens[0].lower() in edge_fillers:
            tokens.pop(0)
        while tokens and tokens[-1].lower() in edge_fillers:
            tokens.pop()
        if len(tokens) == 1:
            attached_di = re.fullmatch(r"(?i)di([a-z][a-z\-']{2,})", tokens[0])
            if attached_di:
                tokens[0] = attached_di.group(1)
        return " ".join(tokens).strip(" .,!?:;")

    text = (question or "").strip()
    if not text:
        return None

    patterns = (
        r"(?i)\b(?:di|in)\s+([^\W\d_][\w\s\-,'\.]{1,120})",
        r"(?i)\b(?:cuaca|weather|suhu|temperature|forecast|prakiraan|ramalan|derajat|degree|degrees|celsius|fahrenheit)\b(?:\s+(?:di|in))?\s+([^\W\d_][\w\s\-,'\.]{1,120})",
    )

    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = _normalize_location_candidate(match.group(1))
        if candidate:
            return _format_location(candidate)

    candidate = re.sub(
        r"(?i)\b(tolong|please|cek|check|semak|cuaca|weather|suhu|temperature|forecast|prakiraan|ramalan|derajat|degree|degrees|celsius|fahrenheit|hari ini|today|right now|sekarang|now|dong|ya|esok|berapa|how much|what is|what's|saat ini|right|gimana|bagaimana|kenapa|kok|kalau|kalo|coba|can|could|why|bisa|bisakah)\b",
        " ",
        text,
    )
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,!?:;")
    candidate = _strip_weather_terms(candidate)
    candidate = _normalize_location_candidate(candidate)
    if not candidate:
        return None
    return _format_location(candidate)


def extract_reminder_message(question: str) -> str:
    """Extract reminder payload text from natural-language query."""
    text = (question or "").strip()
    if not text:
        return "Reminder"

    text = re.sub(r"(?i)^(tolong|please)\s+", "", text)
    text = re.sub(
        r"(?i)\b(remind(?: me)?(?: to)?|ingatkan(?: saya)?(?: untuk)?|buat(?:kan)? pengingat|pengingat|set(?: sekarang)?)\b",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:dalam|in)?\s*\d+\s*(menit|jam|detik|hari|min(?:ute)?s?|hours?|sec(?:ond)?s?|days?)\b(?:\s+lagi)?",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:setiap|tiap|every)\s+\d+\s*(detik|menit|jam|hari|sec(?:ond)?s?|min(?:ute)?s?|hours?|days?)\b(?:\s+sekali)?",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:setiap\s+hari|tiap\s+hari|every\s+day|daily)\b(?:\s*(?:jam|pukul|at))?\s*\d{1,2}(?::\d{2})?",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\b(?:setiap|tiap|every)\s+(?:senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s*(?:jam|pukul|at))?\s*\d{1,2}(?::\d{2})?",
        " ",
        text,
    )
    text = re.sub(r"(?i)\b(lagi|from now|sekarang|now)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,!?:;")

    if not text:
        return "Reminder"
    if len(text) > 180:
        text = text[:180].rstrip()
    return text


def parse_time_token(token: str) -> tuple[int, int] | None:
    """Parse HH[:.]MM or HH token into (hour, minute)."""
    raw = (token or "").strip()
    if not raw:
        return None

    normalized = raw.replace(".", ":")
    if ":" in normalized:
        parts = normalized.split(":", 1)
        if len(parts) != 2:
            return None
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return None
    else:
        try:
            hour = int(normalized)
        except ValueError:
            return None
        minute = 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def extract_cycle_anchor_date(question: str) -> datetime:
    """Resolve cycle anchor date from natural-language hints."""
    now_local = datetime.now().astimezone()
    q_lower = (question or "").lower()

    explicit_iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", q_lower)
    if explicit_iso:
        try:
            date_part = datetime.strptime(explicit_iso.group(1), "%Y-%m-%d")
            return now_local.replace(
                year=date_part.year,
                month=date_part.month,
                day=date_part.day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        except ValueError:
            pass

    explicit_dmy = re.search(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b", q_lower)
    if explicit_dmy:
        try:
            day = int(explicit_dmy.group(1))
            month = int(explicit_dmy.group(2))
            year = int(explicit_dmy.group(3))
            return now_local.replace(
                year=year,
                month=month,
                day=day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        except ValueError:
            pass

    if "lusa" in q_lower:
        return (now_local + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    if "besok" in q_lower or "tomorrow" in q_lower:
        return (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return now_local.replace(hour=0, minute=0, second=0, microsecond=0)


def extract_explicit_schedule_title(question: str) -> str | None:
    """Extract explicit schedule title from phrases like 'judul ...' or 'title ...'."""
    text = (question or "").strip()
    if not text:
        return None

    match = re.search(
        r'(?i)\b(?:judul|title|nama jadwal|schedule name)\b\s*[:=]?\s*[\"\']?([^\"\',;\n]+)',
        text,
    )
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
    return title or None


def extract_new_schedule_title(question: str) -> str | None:
    """Extract rename target from phrases like 'ubah judul jadi ...'."""
    text = (question or "").strip()
    if not text:
        return None
    match = re.search(
        r'(?i)\b(?:ubah judul|rename|rename to|judul baru|new title)\b(?:\s+grp_[a-z0-9_-]+)?\s*(?:jadi|to)\s*[\"\']?([^\"\',;\n]+)',
        text,
    )
    if not match:
        match = re.search(
            r'(?i)\b(?:ubah judul|rename|rename to|judul baru|new title)\b\s*[:=]\s*[\"\']?([^\"\',;\n]+)',
            text,
        )
    if not match:
        return None
    value = re.sub(r"\s+", " ", match.group(1)).strip(" .,!?:;")
    return value or None


def make_unique_schedule_title(base_title: str, existing_titles: Iterable[str]) -> str:
    """Ensure title uniqueness against current cron groups."""
    base = re.sub(r"\s+", " ", (base_title or "").strip())
    if not base:
        base = "Schedule"

    existing_lower = {title.casefold() for title in existing_titles if title}
    if base.casefold() not in existing_lower:
        return base

    idx = 2
    while True:
        candidate = f"{base} ({idx})"
        if candidate.casefold() not in existing_lower:
            return candidate
        idx += 1


def build_group_id(title: str, now_ms: int | None = None) -> str:
    """Build stable-ish unique group id from title + timestamp."""
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    if not slug:
        slug = "schedule"
    slug = slug[:24]
    stamp = now_ms if now_ms is not None else int(datetime.now().timestamp() * 1000)
    return f"grp_{slug}_{stamp % 1_000_000:06d}"


def extract_cycle_schedule(question: str) -> dict[str, Any] | None:
    """Extract complex repeating cycle schedules (shift/work/rest blocks)."""
    text = (question or "").strip()
    if not text:
        return None

    lowered = text.lower()
    if "selama" not in lowered:
        return None
    if not any(k in lowered for k in ("libur", "berulang", "repeat", "cycle", "siklus")):
        return None

    chunks = [
        chunk.strip(" .,!?:;")
        for chunk in re.split(
            r"(?i)\b(?:setelah itu|setelahnya|lalu|kemudian|dan besoknya|besoknya|terus)\b|[,;]",
            text,
        )
        if chunk and chunk.strip(" .,!?:;")
    ]
    if not chunks:
        return None

    segments: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_lower = chunk.lower()
        if "libur" in chunk_lower:
            off_match = re.search(r"(?i)\b(\d+)\s*hari\b", chunk)
            off_days = int(off_match.group(1)) if off_match else 1
            if off_days > 0:
                segments.append({"type": "off", "days": off_days})
            continue

        days_match = re.search(r"(?i)\b(\d+)\s*hari\b", chunk)
        if not days_match:
            continue
        days = int(days_match.group(1))
        if days <= 0:
            continue

        start_time: tuple[int, int] | None = None
        end_time: tuple[int, int] | None = None

        range_match = re.search(
            r"(?i)(\d{1,2}(?:[:.]\d{2})?)\s*(?:-|sampai|hingga|to)\s*(\d{1,2}(?:[:.]\d{2})?)",
            chunk,
        )
        if range_match:
            start_time = parse_time_token(range_match.group(1))
            end_time = parse_time_token(range_match.group(2))
        else:
            single_match = re.search(
                r"(?i)(?:jam|pukul|at)\s*(\d{1,2}(?:[:.]\d{2})?)",
                chunk,
            )
            if single_match:
                start_time = parse_time_token(single_match.group(1))
            else:
                bare_match = re.search(r"(?i)\b(\d{1,2}(?:[:.]\d{2})?)\b", chunk)
                if bare_match:
                    start_time = parse_time_token(bare_match.group(1))

        if not start_time:
            continue

        label = chunk
        label = re.sub(r"(?i)\b(\d{1,2}(?:[:.]\d{2})?)\s*(?:-|sampai|hingga|to)\s*(\d{1,2}(?:[:.]\d{2})?)\b", " ", label)
        label = re.sub(r"(?i)\b(?:jam|pukul|at)\s*\d{1,2}(?:[:.]\d{2})?\b", " ", label)
        label = re.sub(r"(?i)\b(?:selama|for)\s*\d+\s*hari\b", " ", label)
        label = re.sub(
            r"(?i)\b(?:ingatkan|ingatkan saya|jadwalkan|masuk|shift|kerja|hari ini|besok|tomorrow|lusa|berulang|repeat|terus)\b",
            " ",
            label,
        )
        label = re.sub(r"\s+", " ", label).strip(" .,!?:;")
        if not label:
            label = "Reminder"

        segments.append(
            {
                "type": "work",
                "days": days,
                "label": label,
                "start": start_time,
                "end": end_time,
            }
        )

    if not segments:
        return None

    period_days = sum(int(seg["days"]) for seg in segments)
    if period_days < 2:
        return None

    work_segments = [seg for seg in segments if seg["type"] == "work"]
    if not work_segments:
        return None

    anchor = extract_cycle_anchor_date(text)
    events: list[dict[str, str]] = []
    day_offset = 0
    for seg in segments:
        days = int(seg["days"])
        if seg["type"] == "off":
            day_offset += days
            continue

        start_h, start_m = seg["start"]
        end = seg.get("end")
        label = str(seg["label"])

        for idx in range(days):
            run_date = anchor + timedelta(days=day_offset + idx)
            start_dt = run_date.replace(hour=start_h, minute=start_m, second=0, microsecond=0)

            if end:
                end_h, end_m = end
                end_dt = run_date.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                if end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                window = f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d}"
                events.append({"start_at": start_dt.isoformat(timespec="seconds"), "message": f"{label} mulai ({window})"})
                events.append({"start_at": end_dt.isoformat(timespec="seconds"), "message": f"{label} selesai ({window})"})
            else:
                events.append({"start_at": start_dt.isoformat(timespec="seconds"), "message": label})
        day_offset += days

    if not events:
        return None

    return {"period_days": period_days, "events": events}


def build_cycle_title(question: str, period_days: int, existing_titles: Iterable[str]) -> str:
    """Build human-friendly unique title for cycle schedules."""
    explicit_title = extract_explicit_schedule_title(question)
    if explicit_title:
        return make_unique_schedule_title(explicit_title, existing_titles)

    q_lower = (question or "").lower()
    if any(k in q_lower for k in ("shift", "pagi", "sore", "malam", "masuk")):
        base = f"Shift Cycle {period_days} Hari"
    else:
        base = f"Reminder Cycle {period_days} Hari"
    return make_unique_schedule_title(base, existing_titles)


def extract_recurring_schedule(question: str) -> dict[str, Any] | None:
    """Extract recurring cron schedule from natural-language query."""
    text = (question or "").strip()
    if not text:
        return None

    interval_match = re.search(
        r"(?i)\b(?:setiap|tiap|every)\s+(\d+)\s*(detik|menit|jam|hari|sec(?:ond)?s?|min(?:ute)?s?|hours?|days?)\b",
        text,
    )
    if interval_match:
        amount = int(interval_match.group(1))
        unit = interval_match.group(2).lower()
        if amount > 0:
            multiplier = 0
            if unit.startswith(("detik", "sec")):
                multiplier = 1
            elif unit.startswith(("menit", "min")):
                multiplier = 60
            elif unit.startswith(("jam", "hour")):
                multiplier = 3600
            elif unit.startswith(("hari", "day")):
                multiplier = 86400

            if multiplier > 0:
                return {"every_seconds": amount * multiplier, "one_shot": False}

    daily_match = re.search(
        r"(?i)\b(?:setiap\s+hari|tiap\s+hari|every\s+day|daily)\b(?:\s*(?:jam|pukul|at))?\s*(\d{1,2})(?::(\d{2}))?",
        text,
    )
    if daily_match:
        hour = int(daily_match.group(1))
        minute = int(daily_match.group(2) or "0")
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"cron_expr": f"{minute} {hour} * * *", "one_shot": False}

    weekday_map = {
        "minggu": 0,
        "sunday": 0,
        "senin": 1,
        "monday": 1,
        "selasa": 2,
        "tuesday": 2,
        "rabu": 3,
        "wednesday": 3,
        "kamis": 4,
        "thursday": 4,
        "jumat": 5,
        "friday": 5,
        "sabtu": 6,
        "saturday": 6,
    }
    weekly_match = re.search(
        r"(?i)\b(?:setiap|tiap|every)\s+(senin|selasa|rabu|kamis|jumat|sabtu|minggu|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s*(?:jam|pukul|at))?\s*(\d{1,2})(?::(\d{2}))?",
        text,
    )
    if weekly_match:
        day = weekday_map.get(weekly_match.group(1).lower())
        hour = int(weekly_match.group(2))
        minute = int(weekly_match.group(3) or "0")
        if day is not None and 0 <= hour <= 23 and 0 <= minute <= 59:
            return {"cron_expr": f"{minute} {hour} * * {day}", "one_shot": False}

    return None

