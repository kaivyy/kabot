"""Constant lexicon and pattern tables for cron fallback intent scoring."""

from __future__ import annotations

import re

REMINDER_KEYWORDS = (
    "remind",
    "reminder",
    "schedule",
    "alarm",
    "timer",
    "wake me",
    "cron",
    "shift",
)

WEATHER_KEYWORDS = (
    "weather",
    "temperature",
    "forecast",
)

STOCK_KEYWORDS = (
    "stock",
    "ticker",
    "ihsg",
    "idx",
    "market cap",
    "dividend",
    "yield",
    "ratio",
    "pe ratio",
    "stocks",
    "equity",
    "shares",
)

CRYPTO_KEYWORDS = (
    "crypto",
    "cryptocurrency",
    "bitcoin",
    "ethereum",
    "btc",
    "eth",
    "token",
    "coin",
    "blockchain",
    "wallet",
    "staking",
    "mining",
)

PROCESS_RAM_KEYWORDS = (
    # Direct RAM check - EN
    "ram usage", "memory usage", "check ram", "check memory",
    "how much ram", "what's using ram", "top memory", "top ram",
    "process memory", "process ram", "process list",
    "ram per app", "task manager",
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
    "spec", "specs", "specification",
    "hardware", "cpu", "gpu",
    "your pc", "your computer",
    "check pc",
    "system info", "sysinfo",
    # --- Disk / Storage free-space queries (ID, EN, MS, TH, ZH) ---
    "ssd", "hdd", "storage", "disk",
    "space ssd", "space hdd",
    "space", "free space",
    "disk space", "disk usage",
    "check disk", "check storage", "check ssd",
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
    "runtime server", "server runtime",
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
    "cleanup", "clean up",
    "free space", "freespace", "free disk",
    "clear cache", "clear temp",
    "disk cleanup", "disk clean",
    "recycle bin", "optimize", "optimise",
    "cleanup pc", "cleanup ssd", "cleanup hdd",
    "free up",
    # Thai
    "ล้าง", "ล้างแคช", "เคลียร์แคช", "ทำความสะอาดดิสก์", "ลบไฟล์ชั่วคราว",
    # Chinese
    "清理", "清理缓存", "清除缓存", "清理磁盘", "磁盘清理", "释放空间",
)

# Avoid routing conflicts with system-info queries (e.g. "check free space").
# Cleanup should require an explicit cleanup/action intent.
CLEANUP_ACTION_KEYWORDS = (
    "cleanup", "clean up",
    "clear cache", "clear temp",
    "disk cleanup", "disk clean",
    "recycle bin", "optimize", "optimise",
    "cleanup pc", "cleanup ssd", "cleanup hdd",
    "free up",
    # Thai
    "ล้าง", "ล้างแคช", "เคลียร์แคช", "ทำความสะอาดดิสก์", "ลบไฟล์ชั่วคราว",
    # Chinese
    "清理", "清理缓存", "清除缓存", "清理磁盘", "磁盘清理", "释放空间",
)

SPEEDTEST_KEYWORDS = (
    "speedtest", "speed test",
    "internet speed", "connection speed", "network speed",
    "ping pc",
)

NEWS_KEYWORDS = (
    # English
    "news", "headline", "breaking news", "latest news", "current events",
    # Simple multilingual anchors
    "noticias", "actualites", "nachrichten", "новости", "新闻", "ข่าว",
)

CHECK_UPDATE_KEYWORDS = (
    "check update",
    "check for update",
    "check for updates",
    "latest version",
    "is there an update",
)

APPLY_UPDATE_KEYWORDS = (
    "update kabot",
    "upgrade kabot",
    "install update kabot",
    "update program kabot",
    "update bot kabot",
    "update server kabot",
)

CRON_MANAGEMENT_OPS = (
    "list",
    "show",
    "delete",
    "remove",
    "edit",
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
)
_RESEARCH_VERB_MARKERS = (
    "search",
    "find",
    "look up",
    "lookup",
    "check",
)
_UPDATE_CHECK_VERBS = (
    "check",
    "show",
    "is there",
)
_UPDATE_CONTEXT_MARKERS = (
    "update",
    "upgrade",
    "version",
    "latest version",
)
_UPDATE_TARGET_MARKERS = (
    "kabot",
    "bot",
    "agent",
    "program",
    "app",
    "server",
)
_UPDATE_APPLY_INTENT_MARKERS = (
    "upgrade",
    "install",
)
_WEATHER_WIND_MARKERS = (
    "wind",
    "windy",
    "windspeed",
    "wind speed",
    "wind direction",
)
_GEO_NEWS_TOPIC_MARKERS = (
    "war",
    "conflict",
    "israel",
    "iran",
    "gaza",
    "ukraine",
    "russia",
    "usa",
)
_GEO_NEWS_STRONG_TOPIC_MARKERS = (
    "war",
    "conflict",
    "israel",
    "iran",
    "gaza",
    "ukraine",
    "russia",
)
_REMINDER_TIME_RE = re.compile(
    r"(?i)\b\d+\s*(min(?:ute)?s?|hour(?:s)?|sec(?:ond)?s?|day(?:s)?)\b"
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
    "TODAY",
    "NOW",
    "BEST",
    "TOP",
    "LIST",
    "BANK",
    "MARKET",
    "STOCK",
    "TICKER",
    "PRICE",
}
_RAM_CAPACITY_MARKERS = (
    "total ram",
    "installed ram",
    "memory capacity",
    "ram capacity",
    "spec",
)
_RAM_USAGE_MARKERS = (
    "usage",
    "per process",
    "top",
    "process",
)
_DISK_SPACE_MARKERS = (
    "free space",
    "disk space",
    "storage",
    "disk usage",
)
_STOCK_VALUE_QUERY_MARKERS = (
    "price",
    "quote",
    "how much",
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
    "setup",
    "movement",
    "history",
    "historical",
    "chart",
    "performance",
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
    "exchange rate",
    "convert",
    "conversion",
    "usd",
    "idr",
    "dollar",
)
_FX_PAIR_MARKERS = (
    "usd idr",
    "usd/idr",
    "usd to idr",
    "usdidr",
)
_FX_CONVERSION_AMOUNT_RE = re.compile(
    r"(?i)\b(?:around|about|roughly)?\s*(\d+(?:[.,]\d+)?)\s*(usd|dollar|dollars)\b"
)
_PERSONAL_CHAT_MARKERS = (
    "age",
    "old",
    "how old",
    "who are you",
    "how are you",
)
_EMAIL_WORKFLOW_MARKERS = (
    "email",
    "gmail",
    "inbox",
    "draft",
    "subject",
    "recipient",
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
_PRODUCTIVITY_OUTPUT_ACTION_MARKERS = (
    "create",
    "make",
    "generate",
)
_PRODUCTIVITY_SCHEDULE_DOC_MARKERS = (
    "schedule",
    "calendar",
    "plan",
    "program",
)
_PRODUCTIVITY_PLAN_SUBJECT_MARKERS = (
    "run",
    "running",
    "workout",
    "study",
    "content",
    "meal",
    "diet",
    "week",
)
_READ_FILE_ACTION_MARKERS = (
    "read file",
    "open file",
    "show file",
    "display file",
    "print file",
    "cat file",
    "cat ",
    "read config",
)
_READ_FILE_SUBJECT_MARKERS = (
    "file",
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
    "check",
    "open",
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
    "directory",
    "subfolder",
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
    r"([a-zA-Z]:[\\/][^\n\r\"']+|\\\\[^\n\r\"']+|(?<![\w])/(?=[^\"'\s]*[\w.])[^\"'\s]+|(?<![\w])~[\\/][^\s\"']+|[\w.\-]+\\[\w .\\/-]+)"
)
_META_FEEDBACK_MARKERS = (
    "why answer",
    "why did you answer",
    "response",
)
_META_TOPIC_MARKERS = (
    "about",
    "topic",
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
    "このタスク",
    "この依頼",
    "这个任务",
    "这个请求",
    "สำหรับงานนี้",
    "สำหรับคำขอนี้",
)
_NON_ACTION_MARKERS = (
    "stop",
    "dont",
    "don't",
    "do not",
    "not now",
    "cancel",
    "no need",
)
