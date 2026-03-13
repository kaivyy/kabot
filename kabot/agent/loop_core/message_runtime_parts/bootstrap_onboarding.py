"""Bootstrap onboarding persistence helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kabot.bus.events import InboundMessage
from kabot.utils.workspace_templates import get_bootstrap_templates

_BOOTSTRAP_STATE_KEY = "bootstrap_onboarding"
_NUMBERED_ANSWER_RE = re.compile(r"^\s*(\d+)\s*[).,:-]?\s*(.+?)\s*$")
_LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z /_-]{1,40})\s*[:=-]\s*(.+?)\s*$")

_TIMEZONE_ALIASES = {
    "asia/jakarta": "Asia/Jakarta",
    "jakarta": "Asia/Jakarta",
    "wib": "Asia/Jakarta",
    "utc+7": "Asia/Jakarta",
    "utc +7": "Asia/Jakarta",
    "asia/makassar": "Asia/Makassar",
    "makassar": "Asia/Makassar",
    "wita": "Asia/Makassar",
    "utc+8": "Asia/Makassar",
    "utc +8": "Asia/Makassar",
    "asia/jayapura": "Asia/Jayapura",
    "jayapura": "Asia/Jayapura",
    "wit": "Asia/Jayapura",
    "utc+9": "Asia/Jayapura",
    "utc +9": "Asia/Jayapura",
}

_IDENTITY_STAGE_MARKERS = (
    "what should i be called",
    "who am i",
    "what kind of creature",
    "pick my signature",
    "kamu mau panggil aku apa",
    "aku ini makhluk apa",
    "vibe-ku",
    "emoji signature",
    "signature-ku",
)
_USER_STAGE_MARKERS = (
    "aku panggil kamu siapa",
    "what should i call you",
    "what do i call you",
    "what to call them",
    "timezone kamu",
    "timezone you",
    "timezone tetap",
)
_COMPLETE_STAGE_MARKERS = (
    "aku simpan ke profil",
    "simpan ke profilku",
    "saved to profile",
    "next chat aku langsung nyambung",
    "langsung nyambung",
    "mau aku bantu apa dulu",
    "what can i help with",
    "how can i help",
)


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _normalize_timezone(value: str) -> str:
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        return ""
    lowered = raw.lower()
    for alias, resolved in _TIMEZONE_ALIASES.items():
        if alias in lowered:
            return resolved
    if "/" in raw and len(raw) <= 64:
        return raw
    return raw


def _display_case(value: str) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    if not cleaned:
        return ""
    if "/" in cleaned or cleaned.startswith("http"):
        return cleaned
    if cleaned.isupper():
        return cleaned
    return cleaned[:1].upper() + cleaned[1:]


def _display_name(value: str) -> str:
    cleaned = " ".join(str(value or "").strip().split())
    if not cleaned:
        return ""
    return " ".join(part[:1].upper() + part[1:] if part else "" for part in cleaned.split(" "))


def _clean_answer_value(value: str) -> str:
    cleaned = str(value or "").strip()
    cleaned = cleaned.strip(" ,")
    cleaned = re.sub(r"^(?:ya|yes|iya)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_answer_lines(text: str) -> tuple[dict[int, str], list[str], dict[str, str]]:
    numbered: dict[int, str] = {}
    plain: list[str] = []
    labeled: dict[str, str] = {}

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _NUMBERED_ANSWER_RE.match(line)
        if match:
            numbered[int(match.group(1))] = _clean_answer_value(match.group(2))
            continue

        line = re.sub(r"^(?:[-*]|[•])\s*", "", line).strip()
        label_match = _LABEL_RE.match(line)
        if label_match:
            labeled[_normalize_text(label_match.group(1))] = _clean_answer_value(label_match.group(2))
            continue
        plain.append(_clean_answer_value(line))

    return numbered, plain, labeled


def _resolve_stage_from_response(final_content: str, current_stage: str) -> str:
    normalized = _normalize_text(final_content)
    if not normalized:
        return current_stage
    if any(marker in normalized for marker in _COMPLETE_STAGE_MARKERS):
        return "complete"
    if any(marker in normalized for marker in _USER_STAGE_MARKERS):
        return "user"
    if any(marker in normalized for marker in _IDENTITY_STAGE_MARKERS):
        return "identity"
    return current_stage


def _bootstrap_state(session: Any) -> dict[str, Any]:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return {}
    current = metadata.get(_BOOTSTRAP_STATE_KEY)
    if isinstance(current, dict):
        state = dict(current)
    else:
        state = {}
    state.setdefault("assistant", {})
    state.setdefault("user", {})
    state.setdefault("stage", "identity")
    return state


def _save_bootstrap_state(session: Any, state: dict[str, Any]) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    metadata[_BOOTSTRAP_STATE_KEY] = state


def _apply_labeled_answers(state: dict[str, Any], labeled: dict[str, str]) -> None:
    assistant = state.setdefault("assistant", {})
    user = state.setdefault("user", {})
    for label, value in labeled.items():
        if not value:
            continue
        if any(key in label for key in ("nama saya", "my name", "what to call", "panggil saya")):
            user["name"] = value
            user.setdefault("address", value)
        elif "timezone" in label or "zona waktu" in label or label == "wib":
            user["timezone"] = _normalize_timezone(value or label)
        elif any(key in label for key in ("creature", "role", "peran", "makhluk")):
            assistant["creature"] = value
        elif "vibe" in label or "gaya" in label or "tone" in label or "style" in label:
            assistant["vibe"] = value
        elif "emoji" in label or "signature" in label:
            assistant["emoji"] = value
        elif any(key in label for key in ("nama assistant", "assistant name", "panggil aku", "call me")):
            assistant["name"] = value
        elif label == "name" or label == "nama":
            if state.get("stage") == "user":
                user["name"] = value
                user.setdefault("address", value)
            else:
                assistant["name"] = value


def _fill_sequence(target: dict[str, str], fields: tuple[str, ...], answers: list[str]) -> None:
    pending_fields = [field for field in fields if not str(target.get(field) or "").strip()]
    for field, answer in zip(pending_fields, answers):
        if answer:
            target[field] = answer


def _apply_sequential_answers(state: dict[str, Any], numbered: dict[int, str], plain: list[str]) -> None:
    assistant = state.setdefault("assistant", {})
    user = state.setdefault("user", {})
    stage = str(state.get("stage") or "identity").strip().lower() or "identity"

    ordered_numbered = [value for _, value in sorted(numbered.items()) if value]

    if stage == "identity":
        if len(ordered_numbered) >= 6:
            _fill_sequence(assistant, ("name", "creature", "vibe", "emoji"), ordered_numbered[:4])
            _fill_sequence(user, ("name", "timezone"), ordered_numbered[4:6])
            user.setdefault("address", user.get("name", ""))
            if user.get("timezone"):
                user["timezone"] = _normalize_timezone(user["timezone"])
            return
        if ordered_numbered:
            _fill_sequence(assistant, ("name", "creature", "vibe", "emoji"), ordered_numbered)
        elif plain:
            _fill_sequence(assistant, ("name", "creature", "vibe", "emoji"), plain)
    else:
        if ordered_numbered:
            _fill_sequence(user, ("name", "timezone"), ordered_numbered)
        elif plain:
            _fill_sequence(user, ("name", "timezone"), plain)
        user.setdefault("address", user.get("name", ""))
        if user.get("timezone"):
            user["timezone"] = _normalize_timezone(user["timezone"])


def _render_identity_text(state: dict[str, Any]) -> str:
    assistant = state.get("assistant", {})
    name = _display_name(str(assistant.get("name") or "")) or "_(pick something you like)_"
    creature = _display_case(str(assistant.get("creature") or "")) or "_(AI? robot? ghost in the machine?)_"
    vibe = _display_case(str(assistant.get("vibe") or "")) or "_(sharp? warm? playful? calm?)_"
    emoji = _display_case(str(assistant.get("emoji") or "")) or "_(your signature)_"
    return (
        "# IDENTITY.md - Who Am I?\n\n"
        "_Fill this in during your first conversation. Make it yours._\n\n"
        f"- **Name:**\n  {name}\n"
        f"- **Creature:**\n  {creature}\n"
        f"- **Vibe:**\n  {vibe}\n"
        f"- **Emoji:**\n  {emoji}\n"
        "- **Avatar:**\n  _(workspace-relative path, http(s) URL, or data URI)_\n\n"
        "---\n\n"
        "This is not just metadata. It is the start of figuring out who you are.\n"
    )


def _render_user_text(state: dict[str, Any]) -> str:
    user = state.get("user", {})
    name = _display_name(str(user.get("name") or ""))
    address = _display_name(str(user.get("address") or name or ""))
    timezone = str(user.get("timezone") or "")
    return (
        "# USER.md - About Your Human\n\n"
        "_Learn about the person you are helping. Update this as you go._\n\n"
        f"- **Name:**\n  {name}\n"
        f"- **What to call them:**\n  {address}\n"
        "- **Pronouns:** _(optional)_\n"
        f"- **Timezone:**\n  {timezone}\n"
        "- **Notes:**\n  Prefers concise communication.\n\n"
        "## Context\n\n"
        "_(What do they care about? What are they building? What annoys them? Build this over time.)_\n"
    )


def _is_bootstrap_complete(state: dict[str, Any]) -> bool:
    assistant = state.get("assistant", {})
    user = state.get("user", {})
    return all(str(assistant.get(key) or "").strip() for key in ("name", "creature", "vibe", "emoji")) and all(
        str(user.get(key) or "").strip() for key in ("name", "timezone")
    )


def update_bootstrap_onboarding_state(
    loop: Any,
    session: Any,
    msg: InboundMessage,
    final_content: str | None,
    *,
    now_ts: float,
) -> None:
    workspace = getattr(loop, "workspace", None)
    if not isinstance(workspace, Path):
        return

    workspace.mkdir(parents=True, exist_ok=True)
    templates = get_bootstrap_templates(workspace)
    for filename in ("IDENTITY.md", "USER.md"):
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(templates[filename], encoding="utf-8")
    bootstrap_path = workspace / "BOOTSTRAP.md"
    state = _bootstrap_state(session)
    bootstrap_active = bootstrap_path.exists() or str(state.get("stage") or "") != "complete"
    if not bootstrap_active:
        return

    raw_content = str(getattr(msg, "content", "") or "").strip()
    state["updated_at"] = now_ts

    if raw_content and not (raw_content.startswith("/") and len(raw_content.splitlines()) == 1):
        numbered, plain, labeled = _extract_answer_lines(raw_content)
        _apply_labeled_answers(state, labeled)
        _apply_sequential_answers(state, numbered, plain)

    assistant_state = state.setdefault("assistant", {})
    user_state = state.setdefault("user", {})
    session_metadata = getattr(session, "metadata", None)
    session_user_profile = (
        session_metadata.get("user_profile")
        if isinstance(session_metadata, dict)
        else None
    )
    if isinstance(session_user_profile, dict):
        profile_name = str(session_user_profile.get("name") or "").strip()
        profile_address = str(session_user_profile.get("address") or "").strip()
        profile_timezone = str(session_user_profile.get("timezone") or "").strip()
        if profile_name and not user_state.get("name"):
            user_state["name"] = profile_name
        if profile_address and not user_state.get("address"):
            user_state["address"] = profile_address
        if profile_timezone and not user_state.get("timezone"):
            user_state["timezone"] = profile_timezone
    if user_state.get("name") and not user_state.get("address"):
        user_state["address"] = user_state["name"]
    if user_state.get("timezone"):
        user_state["timezone"] = _normalize_timezone(str(user_state["timezone"]))
    for key in ("name", "creature", "vibe", "emoji"):
        if assistant_state.get(key):
            assistant_state[key] = str(assistant_state[key]).strip()

    state["stage"] = _resolve_stage_from_response(final_content or "", str(state.get("stage") or "identity"))
    if _is_bootstrap_complete(state):
        state["stage"] = "complete"
        if bootstrap_path.exists():
            bootstrap_path.unlink()

    (workspace / "IDENTITY.md").write_text(_render_identity_text(state), encoding="utf-8")
    (workspace / "USER.md").write_text(_render_user_text(state), encoding="utf-8")
    _save_bootstrap_state(session, state)
