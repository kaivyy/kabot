"""Constant lexicon and pattern tables for cron fallback intent scoring."""

from __future__ import annotations

import re

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
    "analisis",
    "analysis",
    "breakout",
    "pullback",
    "invalidation",
    "entry",
    "exit",
    "entry exit",
    "support",
    "resistance",
    "stop loss",
    "take profit",
    "risk reward",
    "trading plan",
    "scenario",
    "skenario",
    "setup",
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
)
_LIST_DIR_ACTION_MARKERS = (
    "list",
    "show",
    "display",
    "view",
    "lihat",
    "lihatkan",
    "cek",
    "check",
    "tampilkan",
    "tampilin",
    "isi",
    "open",
    "buka",
    "masuk",
    "enter",
    "cd",
    "dir",
    "ls",
    "显示",
    "查看",
    "打开",
    "表示",
    "見せて",
    "みせて",
    "開いて",
    "開く",
    "เปิด",
    "แสดง",
    "ดู",
)
_LIST_DIR_SUBJECT_MARKERS = (
    "folder",
    "direktori",
    "directory",
    "subfolder",
    "subdirektori",
    "文件夹",
    "文件夾",
    "资料夹",
    "資料夾",
    "目录",
    "目錄",
    "フォルダ",
    "ディレクトリ",
    "โฟลเดอร์",
    "ไดเรกทอรี",
)
_LIST_DIR_TARGET_MARKERS = (
    "desktop",
    "downloads",
    "download",
    "documents",
    "document",
    "docs",
    "pictures",
    "photos",
    "music",
    "videos",
    "home",
    "桌面",
    "下载",
    "下載",
    "文档",
    "文件档案",
    "文件檔案",
    "デスクトップ",
    "ダウンロード",
    "書類",
    "ドキュメント",
    "เดสก์ท็อป",
    "ดาวน์โหลด",
    "เอกสาร",
)
_FILELIKE_QUERY_RE = re.compile(
    r"\b[\w\-]+\.(json|ya?ml|toml|ini|cfg|conf|env|md|txt|csv|log|pdf|docx?|xlsx?|py|js|ts|tsx|jsx|html|css|xml)\b",
    re.IGNORECASE,
)
_PATHLIKE_QUERY_RE = re.compile(
    r"([a-zA-Z]:[\\/][^\n\r\"']+|\\\\[^\n\r\"']+|(?<![\w])/[^\"'\s]+|(?<![\w])~[\\/][^\s\"']+|[\w.\-]+\\[\w .\\/-]+)"
)
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
_META_WORKFLOW_REFERENCE_MARKERS = (
    "workflow",
    "workflows",
    "skill",
    "skills",
    "guide",
    "guides",
    "manual",
    "instructions",
    "instruction",
    "playbook",
    "pattern",
    "alur",
    "panduan",
    "petunjuk",
    "instruksi",
    "cara kerja",
    "ワークフロー",
    "スキル",
    "ガイド",
    "手順",
    "工作流",
    "技能",
    "指南",
    "说明",
    "步驟",
    "步骤",
    "เวิร์กโฟลว์",
    "สกิล",
    "คู่มือ",
    "คำแนะนำ",
    "ขั้นตอน",
)
_META_REFERENCE_VERBS = (
    "follow",
    "use",
    "apply",
    "read",
    "refer",
    "consult",
    "study",
    "learn",
    "ikuti",
    "gunakan",
    "pakai",
    "baca",
    "rujuk",
    "pelajari",
    "pakailah",
    "ikuti alur",
    "gunakan alur",
    "参照",
    "使用",
    "按照",
    "跟着",
    "อ่าน",
    "ใช้",
    "ตาม",
    "อ้างอิง",
)
_META_TASK_SCOPE_MARKERS = (
    "for this task",
    "for this request",
    "for this spec",
    "for this job",
    "untuk tugas ini",
    "untuk request ini",
    "untuk permintaan ini",
    "untuk spek ini",
    "untuk spec ini",
    "buat tugas ini",
    "buat request ini",
    "buat permintaan ini",
    "task ini",
    "request ini",
    "permintaan ini",
    "spec ini",
    "spek ini",
    "このタスク",
    "この依頼",
    "这个任务",
    "这个请求",
    "สำหรับงานนี้",
    "สำหรับคำขอนี้",
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
