"""Lightweight user-profile persistence for natural conversational preferences."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from kabot.utils.workspace_templates import get_bootstrap_templates

_SPACE_RE = re.compile(r"\s+")
_SELF_IDENTITY_INTERROGATIVE_RE = re.compile(
    r"(?i)\b("
    r"who|what|call|address|name|am"
    r")\b"
)
_SELF_IDENTITY_SUBJECT_RE = re.compile(r"(?i)\b(i|me|my|mine|myself)\b")
_SELF_IDENTITY_CALL_RE = re.compile(r"(?i)\b(call|address|name)\b")
_SELF_IDENTITY_EXISTENTIAL_RE = re.compile(
    r"(?i)(\bwho\b.*\bi\b.*\bam\b|\bwho\b.*\bam\b.*\bi\b)"
)
_CALL_ME_RE = re.compile(
    r"(?i)\b("
    r"call me|"
    r"address me as|refer to me as"
    r")\b\s+(.+)"
)
_SELF_IDENTITY_ANSWER_RE = re.compile(
    r"(?i)\b("
    r"if i ask(?: you)? who am i[, ]*answer(?: me| with)?|"
    r"if i ask who i am[, ]*answer(?: me| with)?"
    r")\b\s+(.+)"
)
_QUOTED_VALUE_RE = re.compile(r"[\"“”'`]+([^\"“”'`]{1,120})[\"“”'`]+")
_VALUE_STOP_RE = re.compile(
    r"(?i)\s*(?:,|\.|!|\?|$|\b(?:"
    r"please|remember|save|"
    r"and|yes|ok|okay"
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
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if raw.startswith("/"):
        return False
    if len(normalized) > 120:
        return False
    interrogative_turn = bool(raw.endswith(("?", "？")) or _SELF_IDENTITY_INTERROGATIVE_RE.search(normalized))
    if not interrogative_turn:
        return False
    if _SELF_IDENTITY_EXISTENTIAL_RE.search(normalized):
        return True
    return bool(_SELF_IDENTITY_CALL_RE.search(normalized) and _SELF_IDENTITY_SUBJECT_RE.search(normalized))


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
    metadata["user_profile_memory_dirty"] = True

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


async def sync_user_profile_memory(loop: Any, session: Any, *, session_key: str | None = None) -> None:
    """Persist stable user-profile facts into long-term memory when available."""
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    if not bool(metadata.get("user_profile_memory_dirty")):
        return

    facts = build_user_profile_memory_facts(session, limit=4)
    if not facts:
        metadata["user_profile_memory_dirty"] = False
        return

    memory_obj = getattr(loop, "memory", None)
    remember_fact = getattr(memory_obj, "remember_fact", None)
    if not callable(remember_fact):
        return

    synced_facts = metadata.get("user_profile_memory_facts")
    if not isinstance(synced_facts, list):
        synced_facts = []
    synced_set = {
        _normalize_text(str(item))
        for item in synced_facts
        if str(item or "").strip()
    }

    async def _remember(fact: str) -> None:
        result = remember_fact(
            fact=fact,
            category="user_profile",
            session_id=session_key,
            confidence=0.95,
        )
        if asyncio.iscoroutine(result):
            await result

    for fact in facts:
        normalized_fact = _normalize_text(fact)
        if not normalized_fact or normalized_fact in synced_set:
            continue
        try:
            await _remember(fact)
            synced_set.add(normalized_fact)
        except Exception:
            continue

    metadata["user_profile_memory_facts"] = facts
    metadata["user_profile_memory_dirty"] = False
