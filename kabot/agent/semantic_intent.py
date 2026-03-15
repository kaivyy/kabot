from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)
_META_FEEDBACK_RE = re.compile(
    r"(?i)\b("
    r"why|wrong|slow|bug|error|"
    r"not (?:that|stock|weather|web\s*search|websearch|brows(?:e|ing))|"
    r"no web\s*search|not web\s*search|"
    r"correct(?:ing|ion)? (?:the )?(?:chat|conversation)|"
    r"not about|that's not what i asked"
    r")\b"
)
_ADVICE_RE = re.compile(
    r"(?i)\b("
    r"advice|recommend(?:ation)?|recommend|"
    r"which one|what should i use|should i use"
    r")\b"
)
_HR_ZONE_RE = re.compile(
    r"(?i)\b("
    r"hr|heart rate|hr zone|heart rate zone|"
    r"karvonen|max hr|hr max|resting hr"
    r")\b"
)
_HR_ZONE_ACTION_RE = re.compile(
    r"(?i)\b("
    r"calculate|calc|please|zone|age"
    r")\b"
)
_MEMORY_COMMIT_RE = re.compile(
    r"(?i)\b("
    r"save to memory|save this to memory|save that to memory|save this memory|commit to memory|"
    r"save in memory|remember this|remember that"
    r")\b"
)
_MEMORY_SELF_IDENTITY_RE = re.compile(
    r"(?i)\b(?:who am i|who i am|what do you call me)\b"
)
_MEMORY_RECALL_QUERY_RE = re.compile(
    r"(?i)\b(?:who|what|which|when|where|why|how|tell|show|reply|answer)\b"
)
_MEMORY_RECALL_VERB_RE = re.compile(
    r"(?i)\b(?:remember(?:ed)?|save(?:d)?|store(?:d)?|recall|memory|preference(?:s)?|call(?:ed)?|address(?:ed)?)\b"
)
_MEMORY_RECALL_CONTEXT_RE = re.compile(
    r"(?i)\b(?:before|earlier|previous(?:ly)?|prior|last|just)\b"
)
_MEMORY_RECALL_WORK_RE = re.compile(
    r"(?i)\b(?:decide(?:d|s|ion)?|agree(?:d)?|plan(?:ned)?|todo|task|deadline|status)\b"
)
_MEMORY_RECALL_SUBJECT_RE = re.compile(
    r"(?i)\b(?:i|me|my|mine|myself|we|us|our|ours)\b"
)


@dataclass(slots=True)
class SemanticIntentHint:
    kind: str = "none"
    required_tool: str | None = None
    required_tool_query: str | None = None
    clear_pending: bool = False
    reason: str = ""


def _normalize_text(text: str) -> str:
    raw = str(text or "").strip().lower()
    if not raw:
        return ""
    compact = _NON_WORD_RE.sub(" ", raw)
    return _SPACE_RE.sub(" ", compact).strip()


def _is_cjk_or_unspaced_substantive(raw: str) -> bool:
    if any(ch.isspace() for ch in raw):
        return False
    return bool(
        re.search(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F]", raw)
        and len(raw) >= 5
    )


def _is_low_information_turn(text: str, *, max_tokens: int, max_chars: int) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    if _is_cjk_or_unspaced_substantive(raw):
        return False
    if len(normalized) > max_chars:
        return False
    tokens = [token for token in normalized.split(" ") if token]
    return 0 < len(tokens) <= max_tokens


def _looks_like_meta_feedback(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if not _is_low_information_turn(raw, max_tokens=12, max_chars=96):
        return False
    return bool(_META_FEEDBACK_RE.search(normalized))


def _looks_like_advice_request(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if len(normalized) > 180:
        return False
    if not (
        "?" in raw
        or normalized.startswith(("what ", "which ", "should "))
        or _ADVICE_RE.search(normalized)
    ):
        return False
    return bool(_ADVICE_RE.search(normalized))


def _looks_like_hr_zone_or_fitness_calculation(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if len(normalized) > 320 and "from this" not in normalized:
        return False
    return bool(_HR_ZONE_RE.search(normalized) and _HR_ZONE_ACTION_RE.search(normalized))


def _looks_like_memory_recall(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized or raw.startswith("/"):
        return False
    if _MEMORY_SELF_IDENTITY_RE.search(normalized):
        return True
    if len(normalized) > 240:
        return False
    interrogative_turn = bool(
        raw.endswith(("?", "？"))
        or _MEMORY_RECALL_QUERY_RE.search(normalized)
    )
    if _MEMORY_COMMIT_RE.search(normalized) and not interrogative_turn:
        return False
    if not interrogative_turn:
        return False
    has_memory_anchor = bool(_MEMORY_RECALL_VERB_RE.search(normalized))
    has_context_anchor = bool(_MEMORY_RECALL_CONTEXT_RE.search(normalized))
    has_work_anchor = bool(_MEMORY_RECALL_WORK_RE.search(normalized))
    has_subject_anchor = bool(_MEMORY_RECALL_SUBJECT_RE.search(normalized))
    if has_memory_anchor and (has_subject_anchor or has_work_anchor):
        return True
    if has_context_anchor and has_work_anchor:
        return True
    return False


def arbitrate_semantic_intent(
    text: str,
    *,
    parser_tool: str | None,
    pending_followup_tool: str | None = None,
    pending_followup_source: str = "",
    last_tool_context: dict[str, object] | None = None,
    payload_checker: Callable[[str, str], bool] | None = None,
) -> SemanticIntentHint:
    del pending_followup_tool, pending_followup_source, last_tool_context

    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return SemanticIntentHint()

    payload_present = False
    if parser_tool and callable(payload_checker):
        try:
            payload_present = bool(payload_checker(parser_tool, raw))
        except Exception:
            payload_present = False

    if _looks_like_meta_feedback(raw) and not payload_present:
        return SemanticIntentHint(
            kind="meta_feedback",
            clear_pending=True,
            reason="meta_feedback_turn",
        )

    if parser_tool and _looks_like_memory_recall(raw) and not payload_present:
        return SemanticIntentHint(
            kind="memory_recall",
            reason="memory_recall_not_tool",
        )

    if parser_tool == "weather" and _looks_like_hr_zone_or_fitness_calculation(raw):
        return SemanticIntentHint(
            kind="advice_turn",
            reason="hr_zone_not_weather",
        )

    if parser_tool and _looks_like_advice_request(raw):
        return SemanticIntentHint(
            kind="advice_turn",
            reason="advice_without_tool_payload",
        )

    return SemanticIntentHint()
