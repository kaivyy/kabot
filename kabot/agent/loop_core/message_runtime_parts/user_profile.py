"""Lightweight user-profile persistence for natural conversational preferences."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kabot.utils.workspace_templates import get_bootstrap_templates

_SPACE_RE = re.compile(r"\s+")
_SELF_IDENTITY_QUERY_RE = re.compile(
    r"(?i)\b("
    r"who am i|who i am|"
    r"siapa aku|jadi siapa aku|aku siapa"
    r")\b"
)
_CALL_ME_RE = re.compile(
    r"(?i)\b("
    r"call me|panggil aku|panggil saya|sebut aku|sebut saya|"
    r"address me as|refer to me as"
    r")\b\s+(.+)"
)
_SELF_IDENTITY_ANSWER_RE = re.compile(
    r"(?i)\b("
    r"if i ask(?: you)? who am i[, ]*answer(?: me| with)?|"
    r"kalau aku tanya siapa aku[, ]*jawab(?:nya)?|"
    r"jika aku tanya siapa aku[, ]*jawab(?:nya)?"
    r")\b\s+(.+)"
)
_QUOTED_VALUE_RE = re.compile(r"[\"“”'`]+([^\"“”'`]{1,120})[\"“”'`]+")
_VALUE_STOP_RE = re.compile(
    r"(?i)\s*(?:,|\.|!|\?|$|\b(?:"
    r"tolong|please|ingat|remember|save|simpan|"
    r"dan|and|ya|iya|ok|oke|dong|deh"
    r")\b)"
)


def _normalize_text(text: str) -> str:
    return _SPACE_RE.sub(" ", str(text or "").strip()).strip()


def _clean_profile_value(value: str) -> str:
    cleaned = _normalize_text(value)
    cleaned = cleaned.strip(" ,.!?;:-")
    return cleaned


def _extract_preference_value(trailing_text: str) -> str:
    raw = str(trailing_text or "").strip()
    if not raw:
        return ""
    quoted = _QUOTED_VALUE_RE.search(raw)
    if quoted:
        return _clean_profile_value(quoted.group(1))
    match = _VALUE_STOP_RE.search(raw)
    if match:
        raw = raw[: match.start()]
    return _clean_profile_value(raw)


def infer_user_profile_updates(text: str, *, existing_profile: dict[str, Any] | None = None) -> dict[str, str]:
    """Infer stable user-profile preferences from natural language turns."""
    raw = str(text or "").strip()
    if not raw:
        return {}

    profile = dict(existing_profile or {})
    updates: dict[str, str] = {}

    identity_match = _SELF_IDENTITY_ANSWER_RE.search(raw)
    if identity_match:
        answer_value = _extract_preference_value(identity_match.group(2))
        if answer_value:
            updates["self_identity_answer"] = answer_value
            updates.setdefault("address", answer_value)

    call_me_match = _CALL_ME_RE.search(raw)
    if call_me_match:
        address_value = _extract_preference_value(call_me_match.group(2))
        if address_value:
            updates["address"] = address_value

    if not updates:
        return {}

    merged = {**profile, **updates}
    normalized_updates = {
        key: value
        for key, value in merged.items()
        if key in {"address", "self_identity_answer", "name", "timezone"} and str(value or "").strip()
    }
    return normalized_updates


def looks_like_self_identity_recall(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    return bool(_SELF_IDENTITY_QUERY_RE.search(raw))


def resolve_self_identity_fast_reply(session: Any, text: str) -> str | None:
    if not looks_like_self_identity_recall(text):
        return None
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    profile = metadata.get("user_profile")
    if not isinstance(profile, dict):
        return None
    for key in ("self_identity_answer", "address", "name"):
        value = _clean_profile_value(str(profile.get(key) or ""))
        if value:
            return value
    return None


def build_user_profile_memory_facts(session: Any, *, limit: int = 3) -> list[str]:
    """Build stable, recall-friendly facts from the conversational user profile."""
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return []
    profile = metadata.get("user_profile")
    if not isinstance(profile, dict):
        return []

    facts: list[str] = []

    address = _clean_profile_value(str(profile.get("address") or ""))
    if address:
        facts.append(f"User prefers to be addressed as: {address}")

    self_identity = _clean_profile_value(str(profile.get("self_identity_answer") or ""))
    if self_identity and self_identity != address:
        facts.append(f"If the user asks who they are, answer: {self_identity}")

    name = _clean_profile_value(str(profile.get("name") or ""))
    if name and name not in {address, self_identity}:
        facts.append(f"User name: {name}")

    timezone = _clean_profile_value(str(profile.get("timezone") or ""))
    if timezone:
        facts.append(f"User timezone: {timezone}")

    return facts[: max(1, int(limit or 3))]


def _upsert_markdown_field(text: str, label: str, value: str) -> str:
    pattern = re.compile(
        rf"(?ms)(- \*\*{re.escape(label)}:\*\*\s*\n)(.*?)(?=\n- \*\*|\n## |\Z)"
    )
    replacement = rf"\1  {value}\n"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    trimmed = text.rstrip() + "\n"
    return trimmed + f"- **{label}:**\n  {value}\n"


def persist_user_profile(loop: Any, session: Any, text: str, *, now_ts: float) -> dict[str, Any]:
    """Persist lightweight user profile preferences to session metadata and USER.md."""
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return {}

    current_profile = metadata.get("user_profile")
    if not isinstance(current_profile, dict):
        current_profile = {}

    updates = infer_user_profile_updates(text, existing_profile=current_profile)
    if not updates:
        return current_profile

    merged: dict[str, Any] = {**current_profile, **updates, "updated_at": now_ts}
    metadata["user_profile"] = merged

    workspace = getattr(loop, "workspace", None)
    if isinstance(workspace, Path):
        workspace.mkdir(parents=True, exist_ok=True)
        user_path = workspace / "USER.md"
        if user_path.exists():
            user_text = user_path.read_text(encoding="utf-8")
        else:
            user_text = get_bootstrap_templates(workspace)["USER.md"]
        address = _clean_profile_value(str(merged.get("address") or ""))
        if address:
            user_text = _upsert_markdown_field(user_text, "What to call them", address)
        name = _clean_profile_value(str(merged.get("name") or ""))
        if name:
            user_text = _upsert_markdown_field(user_text, "Name", name)
        timezone = _clean_profile_value(str(merged.get("timezone") or ""))
        if timezone:
            user_text = _upsert_markdown_field(user_text, "Timezone", timezone)
        user_path.write_text(user_text, encoding="utf-8")

    sessions = getattr(loop, "sessions", None)
    save_fn = getattr(sessions, "save", None)
    if callable(save_fn):
        try:
            save_fn(session)
        except Exception:
            pass
    return merged
