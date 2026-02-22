"""Shared multilingual keyword lexicon for routing and fallback logic."""

from __future__ import annotations

REMINDER_TERMS = (
    # English
    "remind",
    "reminder",
    "schedule",
    "alarm",
    "timer",
    "wake me",
    # Indonesian
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

WEATHER_TERMS = (
    # English
    "weather",
    "temperature",
    "forecast",
    # Indonesian
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

CRON_MANAGEMENT_OPS = (
    # English + Indonesian
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
    "peringatan",
    "jadual",
    "เตือน",
    "ตาราง",
    "提醒",
    "日程",
    "计划",
)

STOCK_TERMS = (
    "stock", "saham", "ticker", "price", "harga", "market", "ihsg", "idx",
    "market cap", "dividend", "yield", "ratio", "pe ratio",
    "bursa", "efek", "obligasi", "surat berharga",
)

CRYPTO_TERMS = (
    "crypto", "cryptocurrency", "kripto", "bitcoin", "ethereum", "btc", "eth",
    "token", "coin", "blockchain", "wallet", "staking", "mining",
)

