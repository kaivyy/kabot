"""Reference resolution and follow-up helpers for message runtime."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kabot.agent.loop_core.message_runtime_parts.followup import (
    _NON_ACTION_FOLLOWUP_MARKERS,
    _NON_ACTION_TOPIC_MARKERS,
    _PATHLIKE_TEXT_RE,
    _RUNTIME_META_FEEDBACK_MARKERS,
)
from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _ASSISTANT_OFFER_CONTEXT_STOPWORDS,
    _extract_read_file_path_proxy,
    _is_low_information_turn,
    _looks_like_short_confirmation,
    _normalize_text,
)
_OPTION_SELECTION_NUMERIC_RE = re.compile(
    r"^(?:(?:option|number)\s+)?(?P<ref>\d{1,2})$"
)
_OPTION_SELECTION_REFERENCE_RE = re.compile(
    r"\b(?:(?:option|number|the)\s+)?"
    r"(?P<ref>first|second|third|fourth|fifth|\d{1,2})"
    r"(?:\s+one)?\b",
    re.IGNORECASE,
)
_OPTION_SELECTION_ORDINAL_MAP = {
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
_WEATHER_CONTEXT_SIGNAL_RE = re.compile(
    r"(?i)\b("
    r"forecast|hourly|"
    r"weather|temp(?:erature)?|"
    r"wind(?:y|speed| direction)?|"
    r"cloudy|sunny|rain|"
    r"humidity"
    r")\b"
)
_WEATHER_CONTEXT_SIGNAL_FRAGMENTS = ("風", "风", "ลม", "天気", "天气", "อากาศ")
_FILE_CONTEXT_DEICTIC_RE = re.compile(
    r"(?i)\b(?:(?:this|that)\s+"
    r"(?:file|html|css|config|json|yaml|toml|xml|website|webpage)"
    r"|(?:file|html|css|config|json|yaml|toml|xml|website|webpage)\s+(?:this|that))\b"
)
_FILE_CONTEXT_ANALYSIS_RE = re.compile(
    r"(?i)\b(?:font|content|read|open|check|show|display)\b"
)
_FILE_CONTEXT_COMPACT_FRAGMENTS = (
    "这个文件",
    "这个网页",
    "このファイル",
    "このサイト",
    "ไฟล์นี้",
)
_FILE_CONTEXT_COMPACT_ANALYSIS_FRAGMENTS = ("字体", "フォント", "ฟอนต์")

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
    if _looks_like_contextual_followup_request(raw):
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
    # Medium-length substantive requests with a couple overlapping tokens tend to
    # be fresh asks, not genuine acceptance of the prior assistant offer.
    if len(current_tokens) >= 4:
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
    return False


_WEB_SEARCH_DISABLE_PHRASES = (
    "dont", "don't", "do not", "without", "no",
)
_WEB_SEARCH_DIRECT_ANSWER_WORDS = frozenset({
    "just", "direct", "directly", "answer", "explain",
})
_WEB_SEARCH_LANGUAGE_WORDS = frozenset({
    "english", "indonesian", "japanese", "chinese", "mandarin", "thai",
})
_WEB_SEARCH_LANGUAGE_LEAD_WORDS = frozenset({"use", "in", "please"})


def _looks_like_web_search_disable_request(normalized: str) -> bool:
    if "web search" not in normalized:
        return False
    return any(phrase in normalized for phrase in _WEB_SEARCH_DISABLE_PHRASES)


def _looks_like_web_search_direct_answer_request(normalized: str) -> bool:
    tokens = {token for token in normalized.split() if token}
    if not tokens:
        return False
    if normalized in {"answer directly"}:
        return True
    has_directness = bool(tokens & {"just", "direct", "directly"})
    has_answering = bool(tokens & {"answer", "explain"})
    return has_directness and has_answering


def _looks_like_web_search_language_switch(normalized: str) -> bool:
    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return False
    token_set = set(tokens)
    if not (token_set & _WEB_SEARCH_LANGUAGE_WORDS):
        return False
    if not token_set <= (_WEB_SEARCH_LANGUAGE_WORDS | _WEB_SEARCH_LANGUAGE_LEAD_WORDS):
        return False
    return bool(token_set & {"use", "in"})


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
    if _looks_like_web_search_disable_request(normalized):
        return True
    if _looks_like_web_search_language_switch(normalized):
        return True
    if _looks_like_web_search_direct_answer_request(normalized):
        return True
    return False


_ASSISTANT_FOLLOWUP_GENERIC_HELP_RE = re.compile(
    r"(?i)(?:what\s+can\s+i\s+help\s+you\s+with(?:\s+today)?|"
    r"please\s+tell\s+me\s+what\s+you\s+want)"
)
_ASSISTANT_FOLLOWUP_OFFER_LEAD_RE = re.compile(
    r"(?i)(?:\bif\s+you(?:'d| would)?\s+(?:like|want)\b|"
    r"\bif\s+you\s+like\b|"
    r"如果你(?:想|愿意|想要)|"
    r"よければ|必要なら|"
    r"ถ้า(?:ต้องการ|อยาก))"
)
_ASSISTANT_FOLLOWUP_CAPABILITY_RE = re.compile(
    r"(?i)(?:\b(?:i|we)\s+(?:can|could)\b|"
    r"\bcan\s+also\b|"
    r"我(?:也)?可以|可以帮你|(?:お伝え)?できます|ช่วย(?:คุณ)?ได้)"
)
_ASSISTANT_FOLLOWUP_PROMISE_RE = re.compile(
    r"(?i)(?:\b(?:i|we)\s*(?:will|'ll)\b|"
    r"我(?:会|會|来|來)|"
    r"(?:ผม|ฉัน)จะ|เดี๋ยว(?:ผม|ฉัน))"
)
_ASSISTANT_FOLLOWUP_ACTION_RE = re.compile(
    r"(?i)(?:\b(?:give|show|tell|adjust|customi(?:ze|se)|explain|check|review|prepare|draft|"
    r"write|send|share|continue|summari(?:ze|se)|generate|create|build|make|"
    r"send|share|continue|summari(?:ze|se)|generate|create|build|make)\b|"
    r"我(?:给|給|帮|幫|告诉|告訴|调整|調整|说明|說明|检查|檢查)|"
    r"(?:お伝え|調整|説明|確認)できます|"
    r"(?:บอก|เช็ก|ตรวจ|ส่ง|ปรับ))"
)
_ASSISTANT_FOLLOWUP_CHOICE_PROMPT_RE = re.compile(
    r"(?i)(?:\b(?:reply|choose|pick|select)\b.*"
    r"(?:\b(?:number|one)\b|:\s*\d)|"
    r"(?:选|選)(?:一个|一個|哪個)?|"
    r"(?:選んでください|1つ選んでください|一つ選んでください)|"
    r"เลือก(?:หนึ่ง|แบบไหน|ข้อ|อย่าง))"
)
_ASSISTANT_FOLLOWUP_CHOICE_QUESTION_RE = re.compile(
    r"(?i)(?:\b(?:which\s+one)\b|"
    r"选哪个|選哪個|どれ|どちら|เลือกแบบไหน)"
)
_ASSISTANT_FOLLOWUP_CHOICE_INTRO_RE = re.compile(
    r"(?i)(?:\b(?:option|options|choice|choices|version|versions|"
    r"format|style|tone|formal(?:ity)?|mode)\b|"
    r"版本|文体|文體|แบบ)"
)

_SIDE_EFFECT_ACTION_RE = re.compile(
    r"(?i)\b(?:use\s+path|find|search|locate|look\s+for|"
    r"generate|create|build|make|setup|set\s+up|configure|"
    r"prepare|render|export|write|edit|modify|update|install|"
    r"send|share|save|attach|upload)\b"
)
_SIDE_EFFECT_ARTIFACT_RE = re.compile(
    r"(?i)\b(?:folder|directory|dir|path|desktop|downloads|documents|workspace|"
    r"file|document|excel|xlsx|csv|pdf|docx?|spreadsheet|sheet|"
    r"script|code|bot|app|website|landing(?:\s+page)?|workflow|automation|"
    r"config|server|repo(?:sitory)?|project|image|screenshot|screen\s+shot|"
    r"poster|banner|logo|thumbnail|video|mp4|gif|audio|music|ppt|presentation|deck|template|"
    r"chart|report)\b"
)
_SIDE_EFFECT_PROVIDER_RE = re.compile(
    r"(?i)\b(?:imagen|nanobanana|dall-?e|gemini|midjourney|stable\s+diffusion|sora|veo|runway|pika)\b"
)
_SIDE_EFFECT_DELIVERY_RE = re.compile(
    r"(?i)\b(?:workspace|chat(?:\s+(?:this|here))?|"
    r"send\s+it\s+here|save\s+it|save\s+to|"
    r"export|attach|upload|download)\b|"
    r"\.(?:xlsx|csv|pdf|docx?|png|jpe?g|gif|mp4)\b"
)
_PLANNING_REQUEST_RE = re.compile(
    r"(?i)\b(?:schedule|plan|routine|workout\s+plan|meal\s+plan|study\s+plan)\b"
)
_PLANNING_OUTPUT_RE = re.compile(
    r"(?i)\b(?:file|document|pdf|docx?|xlsx|csv|workspace|path|folder|directory|"
    r"save|send|attach|upload|download|export)\b"
)
_CODING_BUILD_ACTION_RE = re.compile(
    r"(?i)\b(?:build|create|make|write|edit|modify|update|develop|implement|scaffold|fix|refactor|debug|"
    r")\b"
)
_CODING_BUILD_ARTIFACT_RE = re.compile(
    r"(?i)\b(?:website|landing(?:\s+page)?|homepage|app|dashboard|frontend|backend|"
    r"ui|ux|component|page|script|code|bot|repo(?:sitory)?|project|"
    r"plugin|extension|api|endpoint|widget)\b"
)
_MESSAGE_DELIVERY_ACTION_RE = re.compile(
    r"(?i)\b(?:send|share|attach|upload)\b"
)
_MESSAGE_DELIVERY_FILE_RE = re.compile(
    r"(?i)\b(?:file|document|report|pdf|xlsx|csv|image|screenshot|screen\s+shot|"
    r"poster|banner|logo|thumbnail|video|gif|audio|music|mp4|png|jpe?g)\b"
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
    r"(?i)\b(?:content(?:s)?|containing|with content)\b"
)

_ASSISTANT_FOLLOWUP_CHOICE_LINE_RE = re.compile(
    r"^\s*(?:\d{1,2}[.)\uFF09\uFF0E\u3002]|[-*\u2022])\s*\S+"
)


_INLINE_NUMBERED_CHOICE_RE = re.compile(r"(?:^|\s)\d{1,2}(?:[.)）．。]|\s*[\(（])", re.UNICODE)
_USER_OPTION_PROMPT_EXPLICIT_CHOOSE_FOR_ME_RE = re.compile(
    r"(?i)\b(?:which\s+one\s+should\s+i\s+choose|which\s+should\s+i\s+choose|"
    r"choose\s+for\s+me|pick\s+for\s+me)\b"
)


def _looks_like_followup_offer_anchor(normalized: str) -> bool:
    if not normalized:
        return False
    if _ASSISTANT_FOLLOWUP_GENERIC_HELP_RE.search(normalized):
        return False
    has_lead = bool(_ASSISTANT_FOLLOWUP_OFFER_LEAD_RE.search(normalized))
    has_capability = bool(_ASSISTANT_FOLLOWUP_CAPABILITY_RE.search(normalized))
    has_promise = bool(_ASSISTANT_FOLLOWUP_PROMISE_RE.search(normalized))
    has_action = bool(_ASSISTANT_FOLLOWUP_ACTION_RE.search(normalized))
    return (has_lead and (has_capability or has_action)) or (has_promise and has_action)


def _looks_like_followup_selection_prompt(normalized: str) -> bool:
    return bool(normalized and _ASSISTANT_FOLLOWUP_CHOICE_PROMPT_RE.search(normalized))


def _looks_like_followup_choice_question(normalized: str) -> bool:
    return bool(normalized and _ASSISTANT_FOLLOWUP_CHOICE_QUESTION_RE.search(normalized))

def _extract_assistant_followup_offer_text(text: str) -> str | None:
    """Extract a concise assistant offer sentence that can anchor a short follow-up."""
    raw = str(text or "").strip()
    if not raw:
        return None

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    normalized_lines = [_normalize_text(line) for line in lines]
    normalized_raw = _normalize_text(raw)

    def _looks_like_option_intro(raw_line: str, normalized: str, next_lines: list[str]) -> bool:
        if not normalized:
            return False
        choice_lines = [
            line for line in next_lines[:4] if _ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line)
        ]
        if len(choice_lines) < 2:
            return False
        if _looks_like_followup_offer_anchor(normalized):
            return True
        if _looks_like_followup_selection_prompt(normalized):
            return True
        if _looks_like_followup_choice_question(normalized):
            return True
        if not bool(_ASSISTANT_FOLLOWUP_CHOICE_INTRO_RE.search(normalized)):
            return False
        stripped = str(raw_line or "").rstrip()
        return stripped.endswith((":", "：", "?", "？"))

    def _has_inline_choice_prompt(normalized: str, raw_value: str) -> bool:
        if not normalized:
            return False
        if len(_INLINE_NUMBERED_CHOICE_RE.findall(raw_value)) < 2:
            return False
        return _looks_like_followup_selection_prompt(
            normalized
        ) or _looks_like_followup_choice_question(normalized)

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
            if _looks_like_followup_selection_prompt(normalized):
                block.append(line)
                continue
            break
        joined = "\n".join(block).strip()
        return joined if joined else None

    if len(lines) > 1:
        for idx, normalized in enumerate(normalized_lines):
            if _looks_like_option_intro(lines[idx], normalized, lines[idx + 1 :]):
                return _collect_followup_block(idx)

        for idx, normalized in enumerate(normalized_lines):
            if _looks_like_followup_offer_anchor(normalized):
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
        if _looks_like_followup_offer_anchor(normalized):
            return candidate
        if _has_inline_choice_prompt(normalized, candidate):
            return candidate
    return None


def _assistant_followup_text_looks_committed_action(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if _ASSISTANT_FOLLOWUP_GENERIC_HELP_RE.search(normalized):
        return False
    has_promise = bool(_ASSISTANT_FOLLOWUP_PROMISE_RE.search(normalized))
    has_action = bool(_ASSISTANT_FOLLOWUP_ACTION_RE.search(normalized))
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
    if _USER_OPTION_PROMPT_EXPLICIT_CHOOSE_FOR_ME_RE.search(normalized):
        return None

    offer_text = _extract_assistant_followup_offer_text(raw)
    if not offer_text:
        return None

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    choice_count = sum(1 for line in lines if _ASSISTANT_FOLLOWUP_CHOICE_LINE_RE.match(line))
    choice_count += len(_INLINE_NUMBERED_CHOICE_RE.findall(raw))
    has_selection_prompt = _looks_like_followup_selection_prompt(
        normalized
    ) or _looks_like_followup_choice_question(normalized)
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

    has_action = bool(_SIDE_EFFECT_ACTION_RE.search(normalized))
    if not has_action:
        return False
    has_artifact = bool(_SIDE_EFFECT_ARTIFACT_RE.search(normalized))
    has_provider = bool(_SIDE_EFFECT_PROVIDER_RE.search(normalized))
    has_delivery = bool(_SIDE_EFFECT_DELIVERY_RE.search(normalized))
    is_lightweight_planning_request = bool(
        _PLANNING_REQUEST_RE.search(normalized)
        and not has_provider
        and not has_delivery
        and not _PLANNING_OUTPUT_RE.search(normalized)
    )
    if is_lightweight_planning_request:
        return False
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
    if _SIDE_EFFECT_PROVIDER_RE.search(normalized):
        return False

    profile = str(route_profile or "").strip().upper()
    explicit_path = _extract_read_file_path_proxy(raw)
    has_code_path = False
    if explicit_path:
        has_code_path = Path(explicit_path).suffix.lower() in _CODING_BUILD_FILE_SUFFIXES

    has_action = bool(_CODING_BUILD_ACTION_RE.search(normalized))
    has_artifact = has_code_path or bool(_CODING_BUILD_ARTIFACT_RE.search(normalized))
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
    has_delivery_action = bool(_MESSAGE_DELIVERY_ACTION_RE.search(normalized))
    if not has_delivery_action:
        return False
    has_file_subject = bool(_extract_read_file_path_proxy(raw)) or bool(
        _MESSAGE_DELIVERY_FILE_RE.search(normalized)
    )
    if not has_file_subject:
        return False
    has_delivery_target = bool(_SIDE_EFFECT_DELIVERY_RE.search(normalized)) or "chat" in normalized or "channel" in normalized
    return has_delivery_target or has_file_subject

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
        r"^(hi|hello|hey|yo)\b",
        r"^good (morning|afternoon|evening|night)\b",
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
    return bool(
        _WEATHER_CONTEXT_SIGNAL_RE.search(normalized)
        or any(fragment in raw for fragment in _WEATHER_CONTEXT_SIGNAL_FRAGMENTS)
    )


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
    if _FILE_CONTEXT_DEICTIC_RE.search(normalized):
        return True
    if any(fragment in raw for fragment in _FILE_CONTEXT_COMPACT_FRAGMENTS):
        return True
    if not _FILE_CONTEXT_ANALYSIS_RE.search(normalized):
        return False
    if _FILELIKE_EXTENSION_RE.search(raw):
        return True
    return any(fragment in raw for fragment in _FILE_CONTEXT_COMPACT_ANALYSIS_FRAGMENTS)
