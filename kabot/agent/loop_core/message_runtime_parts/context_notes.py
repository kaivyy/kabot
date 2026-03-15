"""Context-note and history helpers for message runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.agent.skills_matching import normalize_skill_reference_name
from kabot.agent.loop_core.message_runtime_parts.followup import (
    _FILELIKE_EXTENSION_RE,
    _FILESYSTEM_LOCATION_QUERY_PATTERNS,
    _PATHLIKE_TEXT_RE,
    _SKILL_CREATION_APPROVAL_MARKERS,
    _SKILL_CREATION_FLOW_KEY,
    _SKILL_CREATION_FLOW_TTL_SECONDS,
)
from kabot.agent.loop_core.message_runtime_parts.helpers import (
    _extract_read_file_path_proxy,
    _is_short_context_followup,
    _looks_like_live_research_query,
    _looks_like_side_effect_request,
    _looks_like_short_confirmation,
    _normalize_text,
)
from kabot.agent.loop_core.message_runtime_parts.reference_resolution import (
    _extract_assistant_followup_offer_text,
    _looks_like_contextual_followup_request,
)
from kabot.bus.events import InboundMessage


_RECENT_CREATED_SKILL_PATH_RE = re.compile(
    r"(?:^|[\\/])skills[\\/]+([^\\/]+)[\\/]SKILL\.md$",
    re.IGNORECASE,
)
_EXISTING_SKILL_USE_MARKERS = (
    "pakai skill",
    "gunakan skill",
    "use skill",
    "use the skill",
    "use that skill",
    "run the skill",
    "run that skill",
    "jalankan skill",
    "lanjut pakai skill",
    "lanjutkan pakai skill",
    "pakai skillnya",
    "gunakan skillnya",
    "jalankan skillnya",
)
_ASSISTANT_EXISTING_SKILL_OFFER_MARKERS = (
    "pakai skill ini",
    "gunakan skill ini",
    "use this skill",
    "use that skill",
    "run this skill",
    "run that skill",
)


def _looks_like_filesystem_location_query(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if len(normalized) > 120:
        return False
    return any(re.search(pattern, normalized) for pattern in _FILESYSTEM_LOCATION_QUERY_PATTERNS)


def _build_filesystem_location_context_note(loop: Any, session: Any, last_tool_context: dict[str, Any] | None) -> str:
    workspace = getattr(loop, "workspace", None)
    workspace_path = ""
    if isinstance(workspace, Path):
        workspace_path = str(workspace.expanduser().resolve())
    elif isinstance(workspace, str) and str(workspace).strip():
        try:
            workspace_path = str(Path(workspace).expanduser().resolve())
        except Exception:
            workspace_path = str(workspace).strip()

    last_path = ""
    if isinstance(last_tool_context, dict):
        last_path = str(last_tool_context.get("path") or "").strip()

    lines = ["[System Note: Filesystem location context]"]
    if workspace_path:
        lines.append(f"Current workspace path: {workspace_path}")
    if last_path:
        lines.append(f"Last navigated filesystem path: {last_path}")
    lines.append(
        "Understand the user's language and answer in that language unless they explicitly ask for a different language. If they ask where you are now, use the concrete path context above."
    )
    return "\n".join(lines)


def _build_session_continuity_action_note(
    loop: Any,
    session: Any,
    *,
    last_tool_context: dict[str, Any] | None = None,
    pending_followup_tool: str | None = None,
    pending_followup_source: str = "",
    recent_file_path: str = "",
) -> str:
    session_meta = getattr(session, "metadata", None)
    if not isinstance(session_meta, dict):
        session_meta = {}

    workspace = getattr(loop, "workspace", None)
    workspace_path = ""
    if isinstance(workspace, Path):
        workspace_path = str(workspace.expanduser().resolve())
    elif isinstance(workspace, str) and str(workspace).strip():
        try:
            workspace_path = str(Path(workspace).expanduser().resolve())
        except Exception:
            workspace_path = str(workspace).strip()

    working_directory = str(session_meta.get("working_directory") or "").strip()
    delivery_route = session_meta.get("delivery_route")

    continuity_fields = []
    if working_directory:
        continuity_fields.append(("Current working directory from session", working_directory))
    if isinstance(delivery_route, dict) and delivery_route:
        continuity_fields.append(
            (
                "Current delivery route from session",
                json.dumps(delivery_route, ensure_ascii=False, sort_keys=True),
            )
        )
    if isinstance(last_tool_context, dict):
        last_tool_name = str(last_tool_context.get("tool") or "").strip()
        if last_tool_name:
            tool_bits = [f"tool={last_tool_name}"]
            for key in ("path", "source", "location", "query"):
                value = str(last_tool_context.get(key) or "").strip()
                if value:
                    tool_bits.append(f"{key}={value}")
            continuity_fields.append(("Last grounded tool context", "; ".join(tool_bits)))
    pending_tool_name = str(pending_followup_tool or "").strip()
    if pending_tool_name:
        pending_summary = f"tool={pending_tool_name}"
        pending_source = str(pending_followup_source or "").strip()
        if pending_source:
            pending_summary += f"; source={pending_source}"
        continuity_fields.append(("Pending follow-up tool", pending_summary))
    recent_file = str(recent_file_path or "").strip()
    if recent_file:
        continuity_fields.append(("Recent grounded file path", recent_file))

    if not continuity_fields:
        return ""
    if workspace_path:
        continuity_fields.insert(0, ("Workspace root", workspace_path))

    lines = ["[System Note: Session continuity context]"]
    for label, value in continuity_fields:
        lines.append(f"{label}: {value}")
    lines.extend(
        (
            "Resolve short or follow-up task requests against the grounded session context above before asking the user to repeat paths, file names, folders, or destinations.",
            "Do not rely on fixed language-specific keywords. Understand the user's actual language and intent naturally, including Japanese, Chinese, Thai, Indonesian, English, and mixed-language turns.",
            "If the user is continuing an earlier file, folder, delivery, or tool workflow, stay on that workflow unless they clearly reset or change topic.",
            "Answer in the user's language unless they explicitly ask for a different language.",
        )
    )
    return "\n".join(lines)


def _parent_pathlike(path: str) -> str:
    raw = str(path or "").strip().rstrip("/\\")
    if not raw:
        return ""
    last_sep = max(raw.rfind("/"), raw.rfind("\\"))
    if last_sep <= 0:
        return ""
    return raw[:last_sep]


def _build_grounded_filesystem_inspection_note(
    loop: Any,
    session: Any,
    *,
    last_tool_context: dict[str, Any] | None = None,
    recent_file_path: str = "",
) -> str:
    session_meta = getattr(session, "metadata", None)
    if not isinstance(session_meta, dict):
        session_meta = {}

    workspace = getattr(loop, "workspace", None)
    workspace_path = ""
    if isinstance(workspace, Path):
        workspace_path = str(workspace.expanduser().resolve())
    elif isinstance(workspace, str) and str(workspace).strip():
        try:
            workspace_path = str(Path(workspace).expanduser().resolve())
        except Exception:
            workspace_path = str(workspace).strip()

    working_directory = str(session_meta.get("working_directory") or "").strip()
    last_tool_name = ""
    last_tool_path = ""
    if isinstance(last_tool_context, dict):
        last_tool_name = str(last_tool_context.get("tool") or "").strip()
        last_tool_path = str(last_tool_context.get("path") or "").strip()
    recent_file = str(recent_file_path or "").strip()

    preferred_root = working_directory
    if not preferred_root and last_tool_path:
        if last_tool_name == "read_file" or re.search(r"\.[A-Za-z0-9]{1,12}$", last_tool_path):
            preferred_root = _parent_pathlike(last_tool_path)
        else:
            preferred_root = last_tool_path
    if not preferred_root and recent_file:
        preferred_root = _parent_pathlike(recent_file)
    if not preferred_root:
        preferred_root = workspace_path

    context_lines = []
    if preferred_root:
        context_lines.append(f"Preferred inspection root: {preferred_root}")
    if workspace_path:
        context_lines.append(f"Workspace root: {workspace_path}")
    if working_directory and working_directory != preferred_root:
        context_lines.append(f"Current working directory from session: {working_directory}")
    if last_tool_name:
        tool_summary = f"tool={last_tool_name}"
        if last_tool_path:
            tool_summary += f"; path={last_tool_path}"
        context_lines.append(f"Last grounded tool context: {tool_summary}")
    if recent_file:
        context_lines.append(f"Recent grounded file path: {recent_file}")
    if not context_lines:
        return ""

    lines = ["[System Note: Grounded filesystem inspection]"]
    lines.extend(context_lines)
    lines.extend(
        (
            "This turn requires real filesystem inspection before you explain what the local folder, repo, project, app, config, or workspace docs imply.",
            "Inspect actual evidence first. Start with list_dir, read_file, find_files, or exec on the grounded path above as needed.",
            "After listing the structure, inspect representative files such as README.md, package.json, pyproject.toml, Dockerfile, mkdocs.yml, AGENTS.md, config.json, or other key entry/config/docs files when they exist.",
            "Do not answer with a generic technology guess, a guessed config status, or only restate filenames. Explain the project or local behavior from the inspected evidence.",
            "Answer in the user's language unless they explicitly ask for a different language.",
        )
    )
    return "\n".join(lines)


def _build_temporal_context_note(*, now_local: datetime | None = None) -> str:
    current = now_local or datetime.now().astimezone()
    yesterday = current - timedelta(days=1)
    tomorrow = current + timedelta(days=1)
    next_week = current + timedelta(days=7)

    tz_name = str(current.tzname() or "Local")
    offset = current.utcoffset()
    total_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    tz_offset = f"UTC{sign}{hours:02d}:{minutes:02d}"

    lines = ["[System Note: Temporal context]"]
    lines.append(f"Local timestamp: {current.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Local timezone: {tz_name} ({tz_offset})")
    lines.append(f"Today local date: {current.strftime('%Y-%m-%d')}")
    lines.append(f"Today local weekday: {current.strftime('%A')}")
    lines.append(f"Yesterday local weekday: {yesterday.strftime('%A')}")
    lines.append(f"Tomorrow local weekday: {tomorrow.strftime('%A')}")
    lines.append(f"Seven days from today weekday: {next_week.strftime('%A')}")
    lines.append("Use these exact local-time facts for day/date/time follow-up questions, then answer in the user's language unless they explicitly ask for a different language.")
    return "\n".join(lines)


def _build_explicit_file_analysis_note(path: str) -> str:
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return ""
    return "\n".join(
        (
            "[System Note: Explicit file reference]",
            f"- The user referenced this concrete file path: {normalized_path}",
            "- If the user is asking about the file's contents, structure, styling, config, docs, bootstrap rules, or attributes, call read_file on that path before answering.",
            "- Do not ask the user to resend the file path when it is already present.",
            "- After reading, answer the real question in the user's language unless they explicitly ask for a different language, instead of dumping the file unless they explicitly ask for the raw content.",
        )
    )


def _message_needs_full_skill_context(context_builder: Any, message: str, profile: str) -> bool:
    """Preserve full context when the current turn would auto-load skills."""
    if not str(message or "").strip():
        return False

    skills_loader = getattr(context_builder, "skills", None)
    matcher = getattr(skills_loader, "match_skills", None)
    if not callable(matcher):
        return False

    try:
        matches = matcher(message, profile)
    except TypeError:
        try:
            matches = matcher(message)
        except Exception as exc:
            logger.debug(f"Skill fast-path bypass check failed: {exc}")
            return False
    except Exception as exc:
        logger.debug(f"Skill fast-path bypass check failed: {exc}")
        return False

    if isinstance(matches, (list, tuple, set)):
        return len(matches) > 0
    return False


def _looks_like_explicit_new_request(text: str) -> bool:
    """
    Detect short-but-substantive turns that should not inherit pending follow-up tool state.

    This keeps continuation UX for lightweight confirms ("ya", "gas"), while
    preventing stale tool carry-over for fresh asks like file/config operations.
    """
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return True
    if any(mark in raw for mark in ("?", "Ã¯Â¼Å¸", "Ã‚Â¿", "Ã˜Å¸")):
        return True
    if re.search(r"(https?://|www\.)", normalized):
        return True
    if _FILELIKE_EXTENSION_RE.search(normalized):
        return True
    if _PATHLIKE_TEXT_RE.search(raw):
        return True

    tokens = [part for part in normalized.split(" ") if part]
    has_file_action_marker = any(
        marker in normalized for marker in ("baca", "read", "open", "buka", "lihat", "show", "display", "print", "cat")
    )
    has_file_subject_marker = any(
        marker in normalized for marker in ("config", "settings", "setting", "file", "berkas", "folder", "direktori", "path")
    )
    if has_file_subject_marker and (has_file_action_marker or len(tokens) >= 3):
        return True
    if has_file_action_marker and any(ch in raw for ch in (".", "/", "\\")):
        return True
    if _looks_like_contextual_followup_request(raw):
        return False

    if len(tokens) >= 4 and (
        _looks_like_live_research_query(normalized)
        or _looks_like_side_effect_request(raw)
    ):
        return True

    if len(tokens) >= 4 and any(
        marker in normalized
        for marker in (
            "what",
            "why",
            "how",
            "when",
            "where",
            "which",
            "who",
            "apa",
            "kenapa",
            "gimana",
            "bagaimana",
            "kapan",
            "mana",
            "siapa",
            "berapa",
        )
    ):
        return True
    return False


def _infer_recent_file_path_from_history(history: list[dict[str, Any]]) -> str:
    for item in reversed(history[-10:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        path = _extract_read_file_path_proxy(content)
        if path:
            return path
    return ""


def _infer_recent_created_skill_name_from_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("\\", "/")
    match = _RECENT_CREATED_SKILL_PATH_RE.search(normalized)
    if not match:
        return ""
    return normalize_skill_reference_name(match.group(1))


def _looks_like_existing_skill_use_followup(
    text: str,
    *,
    assistant_offer_text: str = "",
) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if any(marker in normalized for marker in _EXISTING_SKILL_USE_MARKERS):
        return True
    if not (_looks_like_short_confirmation(raw) or _looks_like_contextual_followup_request(raw)):
        return False
    offer_normalized = _normalize_text(assistant_offer_text)
    if not offer_normalized:
        return False
    return any(marker in offer_normalized for marker in _ASSISTANT_EXISTING_SKILL_OFFER_MARKERS)


def _infer_recent_assistant_option_prompt_from_history(history: list[dict[str, Any]]) -> str:
    for item in reversed(history[-10:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role != "assistant":
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        prompt = _extract_assistant_followup_offer_text(content) or ""
        if prompt:
            return prompt
    return ""


def _infer_recent_assistant_answer_from_history(history: list[dict[str, Any]]) -> str:
    for item in reversed(history[-10:]):
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        if role != "assistant":
            continue
        content = str(item.get("content", "") or "").strip()
        if not content:
            continue
        if _extract_assistant_followup_offer_text(content):
            continue
        return content
    return ""


def _get_skill_creation_flow(session: Any, now_ts: float) -> dict[str, Any] | None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    flow = metadata.get(_SKILL_CREATION_FLOW_KEY)
    if not isinstance(flow, dict):
        return None

    request_text = str(flow.get("request_text") or "").strip()
    stage = str(flow.get("stage") or "discovery").strip().lower() or "discovery"
    kind = str(flow.get("kind") or "create").strip().lower() or "create"
    expires_at = flow.get("expires_at")
    try:
        expires_ts = float(expires_at)
    except Exception:
        expires_ts = 0.0

    if not request_text or expires_ts <= now_ts:
        metadata.pop(_SKILL_CREATION_FLOW_KEY, None)
        return None
    return {
        "request_text": request_text,
        "stage": stage,
        "kind": kind,
    }


def _set_skill_creation_flow(
    session: Any,
    request_text: str,
    now_ts: float,
    *,
    stage: str,
    kind: str = "create",
) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_request = str(request_text or "").strip()
    normalized_stage = str(stage or "discovery").strip().lower() or "discovery"
    normalized_kind = str(kind or "create").strip().lower() or "create"
    if not normalized_request:
        return
    metadata[_SKILL_CREATION_FLOW_KEY] = {
        "request_text": normalized_request[:280],
        "stage": normalized_stage,
        "kind": normalized_kind,
        "updated_at": now_ts,
        "expires_at": now_ts + _SKILL_CREATION_FLOW_TTL_SECONDS,
    }


def _clear_skill_creation_flow(session: Any) -> None:
    metadata = getattr(session, "metadata", None)
    if isinstance(metadata, dict):
        metadata.pop(_SKILL_CREATION_FLOW_KEY, None)


def _looks_like_skill_creation_approval(text: str) -> bool:
    raw = str(text or "")
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if _looks_like_short_confirmation(raw):
        return True
    return any(marker in normalized for marker in _SKILL_CREATION_APPROVAL_MARKERS)


def _looks_like_skill_workflow_followup_detail(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if _looks_like_short_confirmation(raw):
        return False
    if _looks_like_contextual_followup_request(raw):
        return True
    if re.search(
        r"(?i)\b("
        r"struktur|structure|alur|flow|template|format|layout|anatomy|"
        r"references?|scripts?|assets?|skill\.?md|workflow"
        r")\b",
        normalized,
    ) and re.search(
        r"(?i)\b(skill|skills|skillnya|skillsnya)\b|skill\.?md|references?/|scripts?/|assets?/",
        normalized,
    ):
        return True

    numbered_lines = 0
    bullet_lines = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d+[.)]\s*\S", stripped):
            numbered_lines += 1
            continue
        if stripped.startswith(("- ", "* ", "• ")):
            bullet_lines += 1
    if numbered_lines >= 2 or bullet_lines >= 2:
        return True

    has_url_sample = bool(re.search(r"(?i)https?://\S+", raw))
    has_json_shape = bool(
        re.search(r'(?m)"[A-Za-z0-9_.-]+"\s*:\s*', raw)
        or (
            "{" in raw
            and "}" in raw
            and ":" in raw
        )
    )
    if (has_url_sample or has_json_shape) and any(mark in raw for mark in ("\n", "{", "}")):
        return True

    tokens = [part for part in normalized.split(" ") if part]
    if len(tokens) >= 6 and not any(mark in raw for mark in ("?", "？", "¿")):
        if any(mark in raw for mark in ("\n", ",", ";", ":")):
            return True
    return False


def _assistant_response_looks_like_skill_plan(text: str) -> bool:
    raw = str(text or "").strip()
    normalized = _normalize_text(raw)
    if not normalized:
        return False

    if any(marker in normalized for marker in ("skill.md", "/skills/", "references/", "scripts/")):
        return True

    bullet_lines = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ", "â€¢ ", "1.", "2.", "3.", "4.")):
            bullet_lines += 1
    if bullet_lines >= 2 and any(
        marker in normalized
        for marker in ("plan", "rencana", "approval", "approve", "setuju", "langkah", "workflow", "implement")
    ):
        return True
    return False


def _update_skill_creation_flow_after_response(
    session: Any,
    msg: InboundMessage,
    final_content: str | None,
    *,
    now_ts: float,
) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return

    msg_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    guard = msg_meta.get("skill_creation_guard")
    if not isinstance(guard, dict):
        return
    if not bool(guard.get("active")):
        return

    request_text = str(guard.get("request_text") or msg.content or "").strip()
    stage = str(guard.get("stage") or "discovery").strip().lower() or "discovery"
    kind = str(guard.get("kind") or "create").strip().lower() or "create"
    approved = bool(guard.get("approved"))

    if approved:
        _set_skill_creation_flow(session, request_text, now_ts, stage="approved", kind=kind)
        return

    if _assistant_response_looks_like_skill_plan(final_content or ""):
        _set_skill_creation_flow(session, request_text, now_ts, stage="planning", kind=kind)
        return

    _set_skill_creation_flow(session, request_text, now_ts, stage=stage, kind=kind)


def _should_store_followup_intent(
    text: str,
    *,
    required_tool: str | None = None,
    decision_profile: str = "GENERAL",
    decision_is_complex: bool = False,
) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if required_tool:
        return True
    # Keep live/current-fact intent even when prompt is short, so
    # confirmations like "ya/gas/ambil sekarang" can continue deterministically.
    if _looks_like_live_research_query(normalized):
        return True
    if _looks_like_short_confirmation(normalized):
        return False
    if _is_short_context_followup(normalized):
        return False
    profile = str(decision_profile or "").strip().upper()
    # Prefer storing follow-up intent for actionable/complex turns only, to avoid
    # carrying unrelated chat context into short confirmations.
    if decision_is_complex:
        return True
    return profile in {"CODING", "RESEARCH"}


def _build_untrusted_context_payload(
    msg: InboundMessage,
    *,
    dropped_count: int,
    dropped_preview: list[str],
) -> dict[str, Any]:
    """Build explicit untrusted metadata payload for prompt hardening."""
    payload: dict[str, Any] = {
        "channel": str(getattr(msg, "channel", "") or ""),
        "chat_id": str(getattr(msg, "chat_id", "") or ""),
        "sender_id": str(getattr(msg, "sender_id", "") or ""),
    }
    for key in ("account_id", "peer_kind", "peer_id", "guild_id", "team_id", "thread_id"):
        value = getattr(msg, key, None)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    if dropped_count > 0:
        payload["queue_merge"] = {
            "dropped_count": dropped_count,
            "preview": dropped_preview[:2],
        }
    meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    raw_meta = meta.get("raw")
    if isinstance(raw_meta, (dict, list, str, int, float, bool)):
        payload["raw_metadata"] = raw_meta
    return payload


def _build_budget_hints(
    *,
    history_limit: int,
    dropped_count: int,
    fast_path: bool,
    skip_history_for_speed: bool,
    token_mode: str,
    probe_mode: bool = False,
) -> dict[str, Any]:
    load_level = "normal"
    if dropped_count > 0 or history_limit <= 12 or fast_path or skip_history_for_speed:
        load_level = "high"
    if dropped_count >= 3 and history_limit <= 8:
        load_level = "critical"
    return {
        "load_level": load_level,
        "history_limit": max(0, int(history_limit)),
        "dropped_count": max(0, int(dropped_count)),
        "fast_path": bool(fast_path),
        "probe_mode": bool(probe_mode),
        "token_mode": str(token_mode or "boros").strip().lower(),
    }


def _resolve_token_mode(perf_cfg: Any) -> str:
    raw = str(
        getattr(perf_cfg, "token_mode", None)
        or getattr(perf_cfg, "economy_mode", None)
        or "boros"
    ).strip().lower()
    if raw in {"hemat", "economy", "eco", "saving", "enabled", "on", "true", "1"}:
        return "hemat"
    return "boros"


async def _schedule_context_truncation_memory_fact(
    loop: Any,
    *,
    session_key: str,
    summary_meta: dict[str, Any] | None,
) -> None:
    if not isinstance(summary_meta, dict):
        return

    summary = str(summary_meta.get("summary") or "").strip()
    if not summary:
        return

    dropped_count = int(summary_meta.get("dropped_count", 0) or 0)
    fingerprint = str(summary_meta.get("fingerprint") or "").strip()
    if not fingerprint:
        fingerprint = hashlib.sha1(summary.encode("utf-8", errors="ignore")).hexdigest()[:16]

    cache = getattr(loop, "_context_truncation_fact_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(loop, "_context_truncation_fact_cache", cache)
    cache_key = str(session_key)
    if cache.get(cache_key) == fingerprint:
        return
    cache[cache_key] = fingerprint
    if len(cache) > 256:
        oldest_key = next(iter(cache.keys()))
        cache.pop(oldest_key, None)

    memory_obj = getattr(loop, "memory", None)
    remember_fact = getattr(memory_obj, "remember_fact", None)
    if not callable(remember_fact):
        return

    fact_text = f"Context compression summary ({dropped_count} dropped): {summary}"

    async def _persist() -> None:
        try:
            result = remember_fact(
                fact=fact_text,
                category="context_compression",
                session_id=session_key,
                confidence=0.55,
            )
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.debug(f"context compression memory save skipped: {exc}")

    pending_tasks = getattr(loop, "_pending_memory_tasks", None)
    if isinstance(pending_tasks, set):
        task = asyncio.create_task(_persist())
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)
        return
    await _persist()
