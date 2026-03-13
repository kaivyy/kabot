"""Reference resolution and follow-up helpers for message runtime."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kabot.agent.loop_core.message_runtime_parts.followup import (
    _FILE_CONTEXT_FOLLOWUP_MARKERS,
    _NON_ACTION_FOLLOWUP_MARKERS,
    _NON_ACTION_TOPIC_MARKERS,
    _PATHLIKE_TEXT_RE,
    _RUNTIME_META_FEEDBACK_MARKERS,
    _WEATHER_CONTEXT_FOLLOWUP_MARKERS,
)
from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _ANSWER_REFERENCE_FOLLOWUP_PHRASES,
    _ASSISTANT_OFFER_CONTEXT_STOPWORDS,
    _CONTEXTUAL_FOLLOWUP_EXACT,
    _CONTEXTUAL_FOLLOWUP_PHRASES,
    _extract_read_file_path_proxy,
    _is_low_information_turn,
    _looks_like_short_confirmation,
    _normalize_text,
    _normalized_contains_marker,
)
_OPTION_SELECTION_NUMERIC_RE = re.compile(
    r"^(?:(?:opsi|option|nomor|number)\s+)?(?P<ref>\d{1,2})$"
)
_OPTION_SELECTION_REFERENCE_RE = re.compile(
    r"\b(?:(?:opsi|option|nomor|number|yang|the)\s+)?"
    r"(?P<ref>pertama|kedua|ketiga|keempat|kelima|first|second|third|fourth|fifth|\d{1,2})"
    r"(?:\s+one)?\b",
    re.IGNORECASE,
)
_OPTION_SELECTION_ORDINAL_MAP = {
    "pertama": "1",
    "kedua": "2",
    "ketiga": "3",
    "keempat": "4",
    "kelima": "5",
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "แรก": "1",
    "หนึ่ง": "1",
    "สอง": "2",
    "สาม": "3",
    "สี่": "4",
    "ห้า": "5",
}
_OPTION_SELECTION_CJK_ORDINAL_RE = re.compile("\\u7b2c(?P<ref>[\\u4e00\\u4e8c\\u4e09\\u56db\\u4e94\\d]{1,2})(?:\\u4e2a|\\u500b|\\u756a|\\u3064\\u76ee)?")
_OPTION_SELECTION_JA_NUMERIC_RE = re.compile("(?P<ref>\\d{1,2})\\u756a")
_OPTION_SELECTION_THAI_NUMERIC_RE = re.compile("\\u0e02\\u0e49\\u0e2d\\s*(?P<ref>\\d{1,2})")
_OPTION_SELECTION_THAI_ORDINAL_RE = re.compile(
    "(?:\\u0e02\\u0e49\\u0e2d\\s*)?(?:\\u0e17\\u0e35\\u0e48)?(?P<ref>\\u0e41\\u0e23\\u0e01|\\u0e2b\\u0e19\\u0e36\\u0e48\\u0e07|\\u0e2a\\u0e2d\\u0e07|\\u0e2a\\u0e32\\u0e21|\\u0e2a\\u0e35\\u0e48|\\u0e2b\\u0e49\\u0e32)"
)

def _tokenize_context_tokens(text: str) -> set[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return set()
    tokens = re.findall(r"\w+", normalized, flags=re.UNICODE)
    result: set[str] = set()
    for token in tokens:
        if not token:
            continue
        if token in _ASSISTANT_OFFER_CONTEXT_STOPWORDS:
            continue
        if token.isdigit():
            result.add(token)
            continue
        if len(token) < 2:
            continue
        result.add(token)
    return result


def _looks_like_assistant_offer_context_followup(text: str, offer_text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if _looks_like_short_confirmation(raw):
        return True
    if not _is_low_information_turn(raw, max_tokens=7, max_chars=96):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    current_tokens = _tokenize_context_tokens(raw)
    offer_tokens = _tokenize_context_tokens(offer_text)
    if not current_tokens or not offer_tokens:
        return False
    return bool(current_tokens & offer_tokens)


def _looks_like_compact_option_reference_turn(
    text: str,
    *,
    max_tokens: int = 8,
    max_chars: int = 96,
    max_unsegmented_chars: int = 24,
) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if len(normalized) > max_chars:
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    if re.search(r"[@#]\w+", normalized):
        return False
    if re.search(r"\d{3,}", normalized):
        return False
    if any(ch in raw for ch in "{}[]=`\\/"):
        return False

    tokens = [part for part in normalized.split() if part]
    if len(tokens) == 0 or len(tokens) > max_tokens:
        return False

    if not any(ch.isspace() for ch in raw):
        if re.search(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F\u0600-\u06FF]", raw):
            return len(raw) <= max_unsegmented_chars
    return True


def _extract_option_selection_reference(text: str) -> str | None:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return None
    if not _looks_like_compact_option_reference_turn(raw, max_tokens=8, max_chars=96):
        return None
    if re.search(r"(https?://|www\.)", normalized):
        return None
    if _PATHLIKE_TEXT_RE.search(raw):
        return None

    numeric_match = _OPTION_SELECTION_NUMERIC_RE.fullmatch(normalized)
    if numeric_match:
        return str(numeric_match.group("ref") or "").strip() or None

    for pattern in (
        _OPTION_SELECTION_CJK_ORDINAL_RE,
        _OPTION_SELECTION_JA_NUMERIC_RE,
        _OPTION_SELECTION_THAI_NUMERIC_RE,
        _OPTION_SELECTION_THAI_ORDINAL_RE,
    ):
        extra_match = pattern.search(raw)
        if not extra_match:
            continue
        ref = str(extra_match.group("ref") or "").strip()
        if not ref:
            continue
        if ref.isdigit():
            return ref
        mapped = _OPTION_SELECTION_ORDINAL_MAP.get(ref)
        if mapped:
            return mapped

    match = _OPTION_SELECTION_REFERENCE_RE.search(normalized)
    if not match:
        return None
    ref = str(match.group("ref") or "").strip().lower()
    if not ref:
        return None
    if ref.isdigit():
        return ref
    return _OPTION_SELECTION_ORDINAL_MAP.get(ref)


def _extract_referenced_answer_item(answer_text: str, reference: str | None) -> str | None:
    raw_answer = str(answer_text or "").strip()
    ref = str(reference or "").strip()
    if not raw_answer or not ref.isdigit():
        return None
    try:
        index = int(ref) - 1
    except Exception:
        return None
    if index < 0:
        return None

    lines = [line.strip() for line in raw_answer.splitlines() if str(line).strip()]
    if index < len(lines):
        return lines[index]

    numbered_matches = re.findall(
        r"(?:^|[\s(])(?:\d{1,2}[.)]|[①②③④⑤⑥⑦⑧⑨⑩])\s*(.+?)(?=(?:\s+\d{1,2}[.)]|\s+[①②③④⑤⑥⑦⑧⑨⑩]|$))",
        raw_answer,
        flags=re.DOTALL,
    )
    normalized_matches = [str(item).strip() for item in numbered_matches if str(item).strip()]
    if index < len(normalized_matches):
        return normalized_matches[index]
    return None


def _looks_like_answer_reference_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    if _extract_option_selection_reference(raw):
        return True
    if any(phrase in normalized for phrase in _ANSWER_REFERENCE_FOLLOWUP_PHRASES):
        return True
    if not _is_low_information_turn(raw, max_tokens=10, max_chars=120):
        return False
    return False


def _looks_like_contextual_followup_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if _extract_option_selection_reference(raw):
        return True
    if not _is_low_information_turn(raw, max_tokens=8, max_chars=96):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    if normalized in _CONTEXTUAL_FOLLOWUP_EXACT:
        return True
    if "trend" in normalized:
        return True
    if re.search(r"\b(untuk|buat|for)\b.+\b(bagaimana|gimana|how)\b", normalized):
        return True
    return any(phrase in normalized for phrase in _CONTEXTUAL_FOLLOWUP_PHRASES)


def _looks_like_web_search_demotion_followup(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if _PATHLIKE_TEXT_RE.search(raw):
        return False
    if len(normalized) > 120:
        return False
    if normalized in {"english", "use english", "in english", "explain", "just explain"}:
        return True
    return any(marker in normalized for marker in _WEB_SEARCH_DEMOTION_FOLLOWUP_MARKERS)


_ASSISTANT_FOLLOWUP_OFFER_LEAD_MARKERS = (
    "if you want",
    "if you'd like",
    "if you would like",
    "if you like",
    "kalau mau",
    "kalau kamu mau",
    "kalau lo mau",
    "kalau lu mau",
    "kalau anda mau",
    "jika mau",
    "jika anda mau",
    "jika kamu mau",
    "jika anda ingin",
    "jika kamu ingin",
    "bila mau",
    "bila anda mau",
    "bila kamu mau",
    "bila anda ingin",
    "bila kamu ingin",
    "kalau ingin",
    "mau aku",
    "mau saya",
    "si quieres",
    "se quiser",
    "si tu veux",
    "si vous voulez",
    "wenn du willst",
    "wenn sie m?chten",
    "如果你想",
    "如果你愿意",
    "如果你想要",
    "よければ",
    "必要なら",
    "ถ้าต้องการ",
    "ถ้าอยาก",
)

_ASSISTANT_FOLLOWUP_OFFER_CAPABILITY_MARKERS = (
    "i can",
    "i can also",
    "can also",
    "aku bisa",
    "aku juga bisa",
    "saya bisa",
    "saya juga bisa",
    "bisa juga",
    "bisa kasih",
    "bisa berikan",
    "bisa bikinin",
    "bisa bantu",
    "aku lanjut",
    "saya lanjut",
    "aku cek",
    "saya cek",
    "lanjut cek",
    "puedo",
    "je peux",
    "ich kann",
    "我也可以",
    "我可以",
    "可以帮你",
    "できます",
    "お伝えできます",
    "ช่วยได้",
    "ช่วยคุณได้",
)

_WEB_SEARCH_DEMOTION_FOLLOWUP_MARKERS = (
    "just explain",
    "explain",
    "jelaskan",
    "jelasin",
    "terangkan",
    "langsung jelasin",
    "just answer",
    "answer directly",
    "tanpa web search",
    "jangan pakai web search",
    "jangan pake web search",
    "ga usah web search",
    "gak usah web search",
    "nggak usah web search",
    "dont use web search",
    "don't use web search",
    "no web search",
    "without web search",
    "use english",
    "in english",
    "pakai bahasa inggris",
    "pake bahasa inggris",
    "english please",
)

_ASSISTANT_FOLLOWUP_OFFER_PROMISE_MARKERS = (
    "i will",
    "i'll",
    "we will",
    "aku akan",
    "saya akan",
    "gue akan",
    "gua akan",
    "akan aku",
    "akan saya",
    "aku langsung",
    "saya langsung",
    "langsung aku",
    "langsung saya",
    "我会",
    "我會",
    "我来",
    "我來",
    "すぐ",
    "このあと",
    "เดี๋ยวผม",
    "เดี๋ยวฉัน",
    "ผมจะ",
    "ฉันจะ",
)

_ASSISTANT_FOLLOWUP_OFFER_ACTION_MARKERS = (
    "buat",
    "buatkan",
    "bikin",
    "bikinkan",
    "generate",
    "kirim",
    "send",
    "share",
    "lanjut",
    "teruskan",
    "siapkan",
    "prepare",
    "susun",
    "tuliskan",
    "cek",
    "buat file",
    "bikin file",
    "file excel",
    "spreadsheet",
    "xlsx",
    "excel",
)

_ASSISTANT_FOLLOWUP_OFFER_EXCLUDE_MARKERS = (
    "what can i help you with today",
    "what can i help you with",
    "apa yang bisa saya bantu",
    "ada yang bisa saya bantu",
    "silakan beri tahu apa yang ingin",
    "tolong beri tahu apa yang ingin",
)

_ASSISTANT_FOLLOWUP_SELECTION_MARKERS = (
    "balas hanya angka",
    "balas angka",
    "balas hanya nomor",
    "silakan balas",
    "silakan pilih",
    "reply with just",
    "reply only with",
    "reply with only",
    "reply with",
    "choose 1",
    "choose one",
    "pick 1",
    "pick one",
    "select 1",
    "select one",
    "选一个",
    "選一個",
    "选择一个",
    "選擇一個",
    "1つ選んでください",
    "一つ選んでください",
    "選んでください",
    "เลือกหนึ่งแบบ",
    "เลือกหนึ่งข้อ",
    "เลือกหนึ่งอย่าง",
)

_ASSISTANT_FOLLOWUP_OPTION_INTRO_MARKERS = (
    "opsi",
    "pilihan",
    "option",
    "options",
    "choice",
    "choices",
    "tingkat formalitas",
    "formalitas",
    "版本",
    "版",
    "文体",
    "文體",
    "แบบ",
)

_SIDE_EFFECT_ACTION_MARKERS = (
    "cari",
    "carikan",
    "buat",
    "buatkan",
    "bikin",
    "bikinkan",
    "find",
    "search",
    "locate",
    "look for",
    "generate",
    "create",
    "build",
    "make",
    "setup",
    "set up",
    "configure",
    "konfigurasi",
    "siapkan",
    "prepare",
    "render",
    "export",
    "write",
    "tulis",
    "edit",
    "ubah",
    "modify",
    "update",
    "install",
    "pasang",
    "kirim",
    "send",
    "share",
    "simpan",
    "save",
    "attach",
    "lampirkan",
    "upload",
    "生成",
    "创建",
    "建立",
    "制作",
    "写",
    "配置",
    "安装",
    "导出",
    "作成",
    "生成",
    "作って",
    "設定",
    "インストール",
    "出力",
    "保存",
    "สร้าง",
    "ทำ",
    "ตั้งค่า",
    "ติดตั้ง",
    "ส่งออก",
    "บันทึก",
    "ส่ง",
)

_SIDE_EFFECT_ARTIFACT_MARKERS = (
    "file",
    "berkas",
    "dokumen",
    "document",
    "excel",
    "xlsx",
    "csv",
    "pdf",
    "doc",
    "docx",
    "spreadsheet",
    "sheet",
    "script",
    "kode",
    "code",
    "bot",
    "app",
    "aplikasi",
    "website",
    "landing page",
    "landing",
    "workflow",
    "automation",
    "otomasi",
    "config",
    "server",
    "repo",
    "project",
    "gambar",
    "image",
    "screenshot",
    "screen shot",
    "tangkapan layar",
    "poster",
    "banner",
    "logo",
    "thumbnail",
    "video",
    "mp4",
    "gif",
    "audio",
    "music",
    "ppt",
    "presentation",
    "deck",
    "template",
    "chart",
    "grafik",
    "laporan",
    "report",
    "jadwal",
    "文件",
    "表格",
    "脚本",
    "配置",
    "图片",
    "图像",
    "海报",
    "视频",
    "文档",
    "ファイル",
    "表計算",
    "スクリプト",
    "画像",
    "ポスター",
    "動画",
    "設定",
    "ไฟล์",
    "สเปรดชีต",
    "สคริปต์",
    "รูป",
    "ภาพ",
    "โปสเตอร์",
    "วิดีโอ",
    "เอกสาร",
)

_SIDE_EFFECT_PROVIDER_MARKERS = (
    "imagen",
    "nanobanana",
    "dall-e",
    "dalle",
    "gemini",
    "midjourney",
    "stable diffusion",
    "sora",
    "veo",
    "runway",
    "pika",
)

_SIDE_EFFECT_DELIVERY_MARKERS = (
    "workspace",
    "chat ini",
    "chat this",
    "chat here",
    "ke sini",
    "kesini",
    "di sini",
    "sini",
    "kirim ke chat",
    "send it here",
    "save it",
    "simpan hasil",
    "simpan di",
    "save to",
    "export",
    "attach",
    "lampirkan",
    "upload",
    "download",
    ".xlsx",
    ".csv",
    ".pdf",
    ".doc",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".mp4",
)

_CODING_BUILD_ACTION_MARKERS = (
    "build",
    "create",
    "make",
    "write",
    "edit",
    "modify",
    "update",
    "develop",
    "implement",
    "scaffold",
    "fix",
    "refactor",
    "debug",
    "buat",
    "buatkan",
    "bikin",
    "bikinkan",
    "tulis",
    "ubah",
    "perbaiki",
    "kembangkan",
)

_CODING_BUILD_ARTIFACT_MARKERS = (
    "website",
    "landing page",
    "landing",
    "homepage",
    "app",
    "aplikasi",
    "dashboard",
    "frontend",
    "backend",
    "ui",
    "ux",
    "component",
    "komponen",
    "page",
    "halaman",
    "script",
    "kode",
    "code",
    "bot",
    "repo",
    "repository",
    "project",
    "proyek",
    "plugin",
    "extension",
    "api",
    "endpoint",
    "widget",
)

_CODING_BUILD_FILE_SUFFIXES = {
    ".html",
    ".css",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
    ".go",
    ".rs",
    ".java",
    ".php",
    ".rb",
    ".json",
    ".yaml",
    ".yml",
    ".md",
}

_INLINE_CONTENT_MARKERS_RE = re.compile(
    r"(?i)\b(?:berisi|isi(?:nya)?|content(?:s)?|containing|with content|dengan isi)\b"
)

_ASSISTANT_FOLLOWUP_CHOICE_LINE_RE = re.compile(
    r"^\s*(?:\d{1,2}[.)\uFF09\uFF0E\u3002]|[-*\u2022])\s*\S+"
)


_INLINE_NUMBERED_CHOICE_RE = re.compile(r"(?:^|\s)\d{1,2}(?:[.)）．。]|\s*[\(（])", re.UNICODE)
_USER_OPTION_PROMPT_SELECTION_MARKERS = (
    *_ASSISTANT_FOLLOWUP_SELECTION_MARKERS,
    "pilih satu",
    "pilih salah satu",
    "pilih ya",
    "pilih dulu",
    "choose one",
    "pick one",
    "select one",
    "选一个",
    "選一個",
    "1つ選んでください",
    "เลือกหนึ่งแบบ",
)

_INLINE_CHOICE_QUESTION_MARKERS = (
    "mau yang",
    "yang mana",
    "pilihanmu",
    "pilihan anda",
    "pilihan kamu",
    "which one",
    "选哪个",
    "選哪個",
    "どれ",
    "どちら",
    "เลือกแบบไหน",
)

_USER_OPTION_PROMPT_EXPLICIT_CHOOSE_FOR_ME_MARKERS = (
    "menurutmu pilih yang mana",
    "menurut anda pilih yang mana",
    "which one should i choose",
    "which should i choose",
    "choose for me",
    "pick for me",
    "pilihkan",
    "pilihin",
    "pilih yang terbaik",
    "rekomendasikan yang mana",
)

def _extract_assistant_followup_offer_text(text: str) -> str | None:
    """Extract a concise assistant offer sentence that can anchor a short follow-up."""
    raw = str(text or "").strip()
    if not raw:
        return None

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    normalized_lines = [_normalize_text(line) for line in lines]
    normalized_raw = _normalize_text(raw)

    def _is_offer_anchor(normalized: str) -> bool:
        if not normalized:
            return False
        if any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_EXCLUDE_MARKERS):
            return False
        has_lead = any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_LEAD_MARKERS)
        has_capability = any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_CAPABILITY_MARKERS)
        has_promise = any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_PROMISE_MARKERS)
        has_action = any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_OFFER_ACTION_MARKERS)
        return (has_lead and has_capability) or (has_promise and has_action)

    def _looks_like_option_intro(normalized: str, next_lines: list[str]) -> bool:
        if not normalized:
            return False
        has_intro_marker = any(
            marker in normalized for marker in _ASSISTANT_FOLLOWUP_OPTION_INTRO_MARKERS
        )
        has_selection_marker = any(
            marker in normalized for marker in _ASSISTANT_FOLLOWUP_SELECTION_MARKERS
        )
        if not (has_intro_marker or has_selection_marker):
            return False
        return any(_ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line) for line in next_lines[:4])

    def _has_inline_choice_prompt(normalized: str, raw_value: str) -> bool:
        if not normalized:
            return False
        if len(_INLINE_NUMBERED_CHOICE_RE.findall(raw_value)) < 2:
            return False
        return any(marker in normalized for marker in _USER_OPTION_PROMPT_SELECTION_MARKERS) or any(
            marker in normalized for marker in _INLINE_CHOICE_QUESTION_MARKERS
        )

    def _collect_followup_block(start_idx: int) -> str | None:
        if start_idx < 0 or start_idx >= len(lines):
            return None
        block = [lines[start_idx]]
        for idx in range(start_idx + 1, min(len(lines), start_idx + 7)):
            line = lines[idx]
            normalized = normalized_lines[idx]
            if _ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line):
                block.append(line)
                continue
            if any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_SELECTION_MARKERS):
                block.append(line)
                continue
            break
        joined = "\n".join(block).strip()
        return joined if joined else None

    if len(lines) > 1:
        for idx, normalized in enumerate(normalized_lines):
            if _looks_like_option_intro(normalized, lines[idx + 1 :]):
                return _collect_followup_block(idx)

        for idx, normalized in enumerate(normalized_lines):
            if _is_offer_anchor(normalized):
                return _collect_followup_block(idx) or lines[idx]

    if _has_inline_choice_prompt(normalized_raw, raw):
        return raw

    candidates = [segment.strip() for segment in re.split(r"(?<=[.!?ã€‚ï¼ï¼Ÿ])\s+|\n+", raw) if segment.strip()]
    if not candidates:
        candidates = [raw]

    for candidate in reversed(candidates[-4:]):
        normalized = _normalize_text(candidate)
        if not normalized or len(candidate) > 260:
            continue
        if _is_offer_anchor(normalized):
            return candidate
        if _has_inline_choice_prompt(normalized, candidate):
            return candidate
    return None


def _assistant_followup_text_looks_committed_action(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if any(_normalized_contains_marker(normalized, marker) for marker in _ASSISTANT_FOLLOWUP_OFFER_EXCLUDE_MARKERS):
        return False
    has_promise = any(
        _normalized_contains_marker(normalized, marker)
        for marker in _ASSISTANT_FOLLOWUP_OFFER_PROMISE_MARKERS
    )
    has_action = any(
        _normalized_contains_marker(normalized, marker)
        for marker in _ASSISTANT_FOLLOWUP_OFFER_ACTION_MARKERS
    )
    return bool(has_promise and has_action)


def _classify_assistant_followup_intent_kind(text: str) -> str:
    return (
        "assistant_committed_action"
        if _assistant_followup_text_looks_committed_action(text)
        else "assistant_offer"
    )


def _extract_user_supplied_option_prompt_text(text: str) -> str | None:
    """Detect user-authored assistant-like option prompts without auto-selecting for them."""
    raw = str(text or "").strip()
    if not raw:
        return None

    normalized = _normalize_text(raw)
    if not normalized:
        return None
    if any(marker in normalized for marker in _USER_OPTION_PROMPT_EXPLICIT_CHOOSE_FOR_ME_MARKERS):
        return None

    offer_text = _extract_assistant_followup_offer_text(raw)
    if not offer_text:
        return None

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    choice_count = sum(1 for line in lines if _ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line))
    choice_count += len(_INLINE_NUMBERED_CHOICE_RE.findall(raw))
    has_selection_prompt = any(marker in normalized for marker in _USER_OPTION_PROMPT_SELECTION_MARKERS)
    if choice_count < 2 or not has_selection_prompt:
        return None
    return raw


def _looks_like_side_effect_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False

    has_action = any(_normalized_contains_marker(normalized, marker) for marker in _SIDE_EFFECT_ACTION_MARKERS)
    if not has_action:
        return False
    has_artifact = any(
        _normalized_contains_marker(normalized, marker)
        for marker in _SIDE_EFFECT_ARTIFACT_MARKERS
    )
    has_provider = any(
        _normalized_contains_marker(normalized, marker)
        for marker in _SIDE_EFFECT_PROVIDER_MARKERS
    )
    has_delivery = any(
        _normalized_contains_marker(normalized, marker)
        for marker in _SIDE_EFFECT_DELIVERY_MARKERS
    )
    return bool(has_provider or (has_artifact and (has_delivery or has_action)))


def _looks_like_coding_build_request(text: str, *, route_profile: str | None = None) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if any(_normalized_contains_marker(normalized, marker) for marker in _SIDE_EFFECT_PROVIDER_MARKERS):
        return False

    profile = str(route_profile or "").strip().upper()
    explicit_path = _extract_read_file_path_proxy(raw)
    has_code_path = False
    if explicit_path:
        has_code_path = Path(explicit_path).suffix.lower() in _CODING_BUILD_FILE_SUFFIXES

    has_action = any(
        _normalized_contains_marker(normalized, marker)
        for marker in _CODING_BUILD_ACTION_MARKERS
    )
    has_artifact = has_code_path or any(
        _normalized_contains_marker(normalized, marker)
        for marker in _CODING_BUILD_ARTIFACT_MARKERS
    )
    if not has_artifact:
        return False
    if not has_action and profile != "CODING":
        return False
    if has_code_path and _INLINE_CONTENT_MARKERS_RE.search(raw):
        return False
    return True


def _looks_like_message_delivery_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    has_delivery_action = any(
        _normalized_contains_marker(normalized, marker)
        for marker in ("kirim", "send", "share", "attach", "lampirkan", "upload")
    )
    if not has_delivery_action:
        return False
    has_delivery_target = any(
        _normalized_contains_marker(normalized, marker)
        for marker in _SIDE_EFFECT_DELIVERY_MARKERS
    ) or "chat" in normalized or "channel" in normalized
    if not has_delivery_target:
        return False
    has_file_subject = bool(_extract_read_file_path_proxy(raw)) or any(
        _normalized_contains_marker(normalized, marker)
        for marker in (
            "file",
            "berkas",
            "dokumen",
            "document",
            "report",
            "pdf",
            "xlsx",
            "csv",
            "gambar",
            "image",
            "screenshot",
            "screen shot",
            "tangkapan layar",
            "ss",
            "poster",
            "banner",
            "logo",
            "thumbnail",
            "video",
            "gif",
            "audio",
            "music",
            "mp4",
            "png",
            "jpg",
            "jpeg",
        )
    )
    return has_file_subject

def _looks_like_closing_acknowledgement(text: str) -> bool:
    """Detect short gratitude/closure replies that should not trigger pending actions."""
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=8, max_chars=80):
        return False

    patterns = (
        r"\b(thanks|thank you|thx|ty)\b",
        r"\b(makasih|mksh|terima kasih|trimakasih)\b",
        r"\b(merci|gracias|arigato|arigatou|obrigad[oa])\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _looks_like_short_greeting_smalltalk(text: str) -> bool:
    """Detect short greeting/opening messages that should reset pending follow-ups."""
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=5, max_chars=48):
        return False
    patterns = (
        r"^(hi|hai|halo|hello|hey|yo)\b",
        r"^(assalamualaikum|salam)\b",
        r"^good (morning|afternoon|evening|night)\b",
        r"^selamat (pagi|siang|sore|malam)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _looks_like_non_action_meta_feedback(text: str) -> bool:
    """Detect short non-action feedback turns that should clear pending continuations."""
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=10, max_chars=96):
        return False
    if "?" in raw:
        return False
    if any(
        re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", normalized)
        for marker in _RUNTIME_META_FEEDBACK_MARKERS
    ):
        return True
    has_non_action = any(marker in normalized for marker in _NON_ACTION_FOLLOWUP_MARKERS)
    if not has_non_action:
        return False
    has_topic = any(marker in normalized for marker in _NON_ACTION_TOPIC_MARKERS)
    return has_topic


def _looks_like_weather_context_followup(text: str) -> bool:
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if len(raw.strip()) > 96:
        return False
    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) > 8:
        return False
    return any(marker in normalized for marker in _WEATHER_CONTEXT_FOLLOWUP_MARKERS)


def _looks_like_file_context_followup(text: str) -> bool:
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if len(raw.strip()) > 120:
        return False
    if _extract_read_file_path_proxy(raw):
        return False
    return any(marker in normalized for marker in _FILE_CONTEXT_FOLLOWUP_MARKERS)


