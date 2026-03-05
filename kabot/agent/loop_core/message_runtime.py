"""Message/session runtime helpers extracted from AgentLoop."""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t
from kabot.bus.events import InboundMessage, OutboundMessage
from kabot.core.command_router import CommandContext
from kabot.i18n.locale import detect_locale


def _runtime_observability_cfg(loop: Any) -> Any:
    return getattr(loop, "runtime_observability", None)


def _emit_runtime_event(loop: Any, event_name: str, **fields: Any) -> None:
    cfg = _runtime_observability_cfg(loop)
    if not cfg or not bool(getattr(cfg, "enabled", True)):
        return
    if not bool(getattr(cfg, "emit_structured_events", True)):
        return
    sample_rate = float(getattr(cfg, "sample_rate", 1.0))
    if sample_rate <= 0:
        return
    if sample_rate < 1.0 and random.random() > sample_rate:
        return
    payload = {"event": event_name, **fields}
    try:
        logger.info(f"runtime_event={json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}")
    except Exception:
        logger.info(f"runtime_event={payload}")


_PENDING_FOLLOWUP_TOOL_KEY = "pending_followup_tool"
_PENDING_FOLLOWUP_INTENT_KEY = "pending_followup_intent"
_PENDING_FOLLOWUP_TTL_SECONDS = 15 * 60
_KEEPALIVE_INITIAL_DELAY_SECONDS = 1.0
_KEEPALIVE_INTERVAL_SECONDS = 4.0
_KEEPALIVE_PASSTHROUGH_CHANNELS = {
    "telegram",
    "discord",
    "signal",
    "matrix",
    "teams",
    "google_chat",
    "mattermost",
    "webex",
    "line",
}
_MUTABLE_STATUS_LANE_CHANNELS = {
    "telegram",
    "discord",
    "slack",
    "signal",
    "matrix",
    "teams",
    "google_chat",
    "mattermost",
    "webex",
    "line",
}
_ABORT_REQUEST_TRIGGERS = {
    "stop",
    "abort",
    "halt",
    "interrupt",
    "exit",
    "wait",
    "please stop",
    "stop please",
    "stop kabot",
    "kabot stop",
    "stop action",
    "stop current action",
    "stop run",
    "stop current run",
    "stop agent",
    "stop the agent",
    "stop do not do anything",
    "stop don't do anything",
    "stop dont do anything",
    "stop doing anything",
    "do not do that",
    # Indonesian / Malay
    "berhenti",
    "hentikan",
    "stop dulu",
    "jangan lakukan itu",
    "jangan lakukan",
    # Spanish / French / German / Portuguese
    "detente",
    "deten",
    "arrete",
    "stopp",
    "anhalten",
    "aufhoren",
    "hoer auf",
    "pare",
    # Chinese / Japanese / Hindi / Arabic / Russian
    "\u505c\u6b62",
    "\u3084\u3081\u3066",
    "\u6b62\u3081\u3066",
    "\u0930\u0941\u0915\u094b",
    "\u062a\u0648\u0642\u0641",
    "\u0441\u0442\u043e\u043f",
    "\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u0438",
    "\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0441\u044c",
    "\u043f\u0440\u0435\u043a\u0440\u0430\u0442\u0438",
}
_TRAILING_ABORT_PUNCT_RE = re.compile(r"[.!?,;:'\"\u2019\u201d)\]\}]+$", re.UNICODE)


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _normalize_abort_trigger_text(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""
    normalized = normalized.replace("\u2019", "'").replace("`", "'")
    while True:
        updated = _TRAILING_ABORT_PUNCT_RE.sub("", normalized).strip()
        if updated == normalized:
            break
        normalized = updated
    return normalized


def _is_abort_request_text(text: str) -> bool:
    normalized = _normalize_abort_trigger_text(text)
    if not normalized:
        return False
    if normalized == "/stop":
        return True
    if normalized.startswith("/stop@") and " " not in normalized:
        return True
    return normalized in _ABORT_REQUEST_TRIGGERS


def _is_low_information_turn(text: str, *, max_tokens: int, max_chars: int) -> bool:
    """
    Detect short follow-up acknowledgements without language-specific keyword catalogs.

    The decision is structural (length + payload shape), so it remains multilingual.
    """
    raw_text = str(text or "")
    normalized = _normalize_text(raw_text)
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if any(mark in raw_text for mark in ("?", "？", "¿", "؟")):
        return False

    tokens = normalized.split()
    if len(tokens) == 0 or len(tokens) > max_tokens:
        return False
    if len(normalized) > max_chars:
        return False

    # Languages/scripts that are commonly written without spaces should not be
    # treated as low-information when the raw utterance is substantive.
    if not any(ch.isspace() for ch in raw_text):
        if re.search(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0E00-\u0E7F\u0600-\u06FF]", raw_text):
            if len(raw_text) >= 5:
                return False

    # Rich payloads usually indicate fresh intent, not lightweight continuation.
    if re.search(r"(https?://|www\.)", normalized):
        return False
    if re.search(r"[@#]\w+", normalized):
        return False
    if re.search(r"\d{3,}", normalized):
        return False
    if any(ch in raw_text for ch in "{}[]=`\\/"):
        return False
    return True


def _normalize_locale_tag(value: Any) -> str | None:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return None
    base = raw.split("-", 1)[0].strip()
    return base or None


def _resolve_runtime_locale(session: Any, msg: InboundMessage, text: str) -> str:
    """Resolve stable runtime locale for per-turn status messaging."""
    session_meta = getattr(session, "metadata", None)
    if not isinstance(session_meta, dict):
        session_meta = {}
        try:
            setattr(session, "metadata", session_meta)
        except Exception:
            pass

    msg_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    explicit = _normalize_locale_tag(
        msg_meta.get("locale") or msg_meta.get("language") or msg_meta.get("lang")
    )
    if explicit:
        session_meta["runtime_locale"] = explicit
        return explicit

    detected = _normalize_locale_tag(detect_locale(text))
    cached = _normalize_locale_tag(session_meta.get("runtime_locale"))
    if detected and detected != "en":
        session_meta["runtime_locale"] = detected
        return detected
    if cached:
        return cached
    return detected or "en"


def _tool_registry_has(loop: Any, tool_name: str) -> bool:
    tools = getattr(loop, "tools", None)
    if tools is None:
        return False
    has_fn = getattr(tools, "has", None)
    if callable(has_fn):
        try:
            return bool(has_fn(tool_name))
        except Exception:
            return False
    names = getattr(tools, "tool_names", None)
    if isinstance(names, list):
        return tool_name in names
    return False


def _channel_supports_keepalive_passthrough(loop: Any, channel_name: str) -> bool:
    """Return whether the current channel should receive periodic keepalive pulses."""
    normalized = str(channel_name or "").strip()
    if not normalized:
        return False

    manager = getattr(loop, "channel_manager", None)
    channels_map = getattr(manager, "channels", None) if manager is not None else None
    if isinstance(channels_map, dict):
        channel_obj = channels_map.get(normalized)
        if channel_obj is None:
            lowered = normalized.lower()
            channel_obj = channels_map.get(lowered)
        if channel_obj is not None:
            allow_keepalive = getattr(channel_obj, "_allow_keepalive_passthrough", None)
            if callable(allow_keepalive):
                try:
                    return bool(allow_keepalive())
                except Exception:
                    pass

    channel_base = normalized.lower().split(":", 1)[0]
    return channel_base in _KEEPALIVE_PASSTHROUGH_CHANNELS


def _channel_uses_mutable_status_lane(loop: Any, channel_name: str) -> bool:
    """Return whether status phases should be emitted as full mutable lifecycle."""
    normalized = str(channel_name or "").strip()
    if not normalized:
        return False

    manager = getattr(loop, "channel_manager", None)
    channels_map = getattr(manager, "channels", None) if manager is not None else None
    if isinstance(channels_map, dict):
        channel_obj = channels_map.get(normalized)
        if channel_obj is None:
            channel_obj = channels_map.get(normalized.lower())
        if channel_obj is not None:
            mutable_status = getattr(channel_obj, "_uses_mutable_status_lane", None)
            if callable(mutable_status):
                try:
                    return bool(mutable_status())
                except Exception:
                    pass

    channel_base = normalized.lower().split(":", 1)[0]
    return channel_base in _MUTABLE_STATUS_LANE_CHANNELS


def _looks_like_live_research_query(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False

    # Time-sensitive or "latest" wording should always force live search.
    live_markers = (
        "latest",
        "today",
        "now",
        "current",
        "breaking",
        "headline",
        "headlines",
        "news",
        "berita",
        "terbaru",
        "terkini",
        "sekarang",
    )
    if any(marker in normalized for marker in live_markers):
        return True

    if re.search(r"\b(news|berita)\s+update(s)?\b", normalized):
        return True

    # Date/year queries generally imply external verification.
    if re.search(r"\b(19|20)\d{2}\b", normalized):
        return True

    # Search verbs in multilingual variants.
    search_verbs = (
        "find",
        "search",
        "look up",
        "cari",
        "carikan",
        "telusuri",
        "buscar",
        "rechercher",
    )
    if any(normalized.startswith(f"{verb} ") for verb in search_verbs):
        return True

    return False


def _is_short_context_followup(text: str) -> bool:
    return _is_low_information_turn(text, max_tokens=6, max_chars=64)


def _looks_like_short_confirmation(text: str) -> bool:
    return _is_low_information_turn(text, max_tokens=4, max_chars=40)


def _get_pending_followup_tool(session: Any, now_ts: float) -> dict[str, str] | None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    pending = metadata.get(_PENDING_FOLLOWUP_TOOL_KEY)
    if not isinstance(pending, dict):
        return None

    tool_name = str(pending.get("tool") or "").strip()
    expires_at = pending.get("expires_at")
    try:
        expires_ts = float(expires_at)
    except Exception:
        expires_ts = 0.0

    if not tool_name or expires_ts <= now_ts:
        metadata.pop(_PENDING_FOLLOWUP_TOOL_KEY, None)
        return None
    source = str(pending.get("source") or "").strip()
    result = {"tool": tool_name}
    if source:
        result["source"] = source
    return result


def _set_pending_followup_tool(session: Any, tool_name: str, now_ts: float, source_text: str) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_source = _normalize_text(source_text)[:160]
    metadata[_PENDING_FOLLOWUP_TOOL_KEY] = {
        "tool": tool_name,
        "source": normalized_source,
        "updated_at": now_ts,
        "expires_at": now_ts + _PENDING_FOLLOWUP_TTL_SECONDS,
    }


def _clear_pending_followup_tool(session: Any) -> None:
    metadata = getattr(session, "metadata", None)
    if isinstance(metadata, dict):
        metadata.pop(_PENDING_FOLLOWUP_TOOL_KEY, None)


def _get_pending_followup_intent(session: Any, now_ts: float) -> dict[str, str] | None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    pending = metadata.get(_PENDING_FOLLOWUP_INTENT_KEY)
    if not isinstance(pending, dict):
        return None

    intent_text = str(pending.get("text") or "").strip()
    profile = str(pending.get("profile") or "").strip().upper() or "GENERAL"
    expires_at = pending.get("expires_at")
    try:
        expires_ts = float(expires_at)
    except Exception:
        expires_ts = 0.0

    if not intent_text or expires_ts <= now_ts:
        metadata.pop(_PENDING_FOLLOWUP_INTENT_KEY, None)
        return None
    return {"text": intent_text, "profile": profile}


def _set_pending_followup_intent(session: Any, intent_text: str, profile: str, now_ts: float) -> None:
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return
    normalized_intent = _normalize_text(intent_text)[:220]
    if not normalized_intent:
        return
    metadata[_PENDING_FOLLOWUP_INTENT_KEY] = {
        "text": normalized_intent,
        "profile": str(profile or "GENERAL").strip().upper(),
        "updated_at": now_ts,
        "expires_at": now_ts + _PENDING_FOLLOWUP_TTL_SECONDS,
    }


def _clear_pending_followup_intent(session: Any) -> None:
    metadata = getattr(session, "metadata", None)
    if isinstance(metadata, dict):
        metadata.pop(_PENDING_FOLLOWUP_INTENT_KEY, None)


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


async def process_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    """Process a regular inbound message."""
    if msg.channel == "system":
        return await process_system_message(loop, msg)

    turn_started = time.perf_counter()
    turn_id = f"{msg.channel}:{msg.chat_id}:{int(msg.timestamp.timestamp() * 1000)}"
    setattr(loop, "_active_turn_id", turn_id)
    _emit_runtime_event(
        loop,
        "turn_start",
        turn_id=turn_id,
        channel=msg.channel,
        chat_id=msg.chat_id,
    )
    perf_cfg = getattr(loop, "runtime_performance", None)

    approval_action = loop._parse_approval_command(msg.content)
    if approval_action:
        action, approval_id = approval_action
        return await process_pending_exec_approval(
            loop,
            msg,
            action=action,
            approval_id=approval_id,
        )

    # OpenClaw-style abort shortcut: standalone stop/cancel intent should
    # immediately halt follow-up continuation and clear pending intent state.
    if _is_abort_request_text(msg.content):
        session = await loop._init_session(msg)
        _clear_pending_followup_tool(session)
        _clear_pending_followup_intent(session)
        runtime_locale = _resolve_runtime_locale(session, msg, msg.content)
        stop_text = t("runtime.abort.ack", locale=runtime_locale, text=msg.content)
        _emit_runtime_event(loop, "turn_abort_shortcut", turn_id=turn_id)
        return await loop._finalize_session(msg, session, stop_text)

    # Phase 8: Intercept slash commands BEFORE routing to LLM
    if loop.command_router.is_command(msg.content):
        ctx = CommandContext(
            message=msg.content,
            args=[],
            sender_id=msg.sender_id,
            channel=msg.channel,
            chat_id=msg.chat_id,
            session_key=msg.session_key,
            agent_loop=loop,
        )
        result = await loop.command_router.route(msg.content, ctx)
        if result:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=result,
            )

    session = await loop._init_session(msg)
    if not bool(getattr(loop, "_cold_start_reported", False)):
        boot_started = getattr(loop, "_boot_started_at", None)
        startup_ready = getattr(loop, "_startup_ready_at", None)
        if isinstance(boot_started, (int, float)) and isinstance(startup_ready, (int, float)):
            cold_start_ms = int((startup_ready - boot_started) * 1000)
            logger.info(f"cold_start_ms={max(0, cold_start_ms)}")
        elif isinstance(boot_started, (int, float)):
            cold_start_ms = int((time.perf_counter() - boot_started) * 1000)
            logger.info(f"cold_start_ms={cold_start_ms}")
        loop._cold_start_reported = True

    # Phase 9: Parse directives from message body
    clean_body, directives = loop.directive_parser.parse(msg.content)
    effective_content = clean_body or msg.content
    intent_source_for_followup = effective_content

    # Store directives in session metadata
    if directives.raw_directives:
        active = loop.directive_parser.format_active_directives(directives)
        logger.info(f"Directives active: {active}")

        session.metadata["directives"] = {
            "think": directives.think,
            "verbose": directives.verbose,
            "elevated": directives.elevated,
        }
        # Ensure metadata persists
        loop.sessions.save(session)

    # Phase 9: Model override via directive
    if directives.model:
        logger.info(f"Directive override: model -> {directives.model}")

    # Phase 13: Detect document uploads and inject hint for KnowledgeLearnTool
    if hasattr(msg, "media") and msg.media:
        document_paths = []
        for path in msg.media:
            ext = Path(path).suffix.lower()
            if ext in [".pdf", ".txt", ".md", ".csv"]:
                document_paths.append(path)

        if document_paths:
            hint = "\n\n[System Note: Document(s) detected: " + ", ".join(document_paths) + ". If the user wants you to 'learn' or 'memorize' these permanently, use the 'knowledge_learn' tool.]"
            effective_content += hint
            logger.info(f"Document hint injected: {len(document_paths)} files")

    required_tool = loop._required_tool_for_query(effective_content)
    required_tool_query = effective_content
    now_ts = time.time()
    is_background_task = (
        (msg.channel or "").lower() == "system"
        or (msg.sender_id or "").lower() == "system"
        or (
            isinstance(msg.content, str)
            and msg.content.strip().lower().startswith("heartbeat task:")
        )
    )

    direct_tools = {
        "get_process_memory",
        "get_system_info",
        "cleanup_system",
        "web_search",
        "weather",
        "speedtest",
        "stock",
        "crypto",
        "server_monitor",
        "check_update",
        "system_update",
    }
    fast_direct_context = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and required_tool in direct_tools
    )

    history_limit = 30
    if perf_cfg and bool(getattr(perf_cfg, "fast_first_response", True)):
        warmup_task = getattr(loop, "_memory_warmup_task", None)
        if warmup_task is not None and not warmup_task.done():
            history_limit = 12
    if fast_direct_context:
        history_limit = min(history_limit, 6)

    conversation_history: list[dict[str, Any]] = []
    skip_history_for_speed = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and _looks_like_live_research_query(effective_content)
    )
    if not fast_direct_context and not skip_history_for_speed:
        conversation_history = loop.memory.get_conversation_context(msg.session_key, max_messages=history_limit)
        if conversation_history:
            conversation_history = [m for m in conversation_history if isinstance(m, dict)]

    # Router triase: SIMPLE vs COMPLEX
    decision = await loop.router.route(effective_content)
    logger.info(f"Route: profile={decision.profile}, complex={decision.is_complex}")
    try:
        msg.metadata["route_profile"] = decision.profile
        msg.metadata["route_complex"] = bool(decision.is_complex)
    except Exception:
        pass

    pending_followup_tool_payload = _get_pending_followup_tool(session, now_ts)
    pending_followup_tool = (
        str(pending_followup_tool_payload.get("tool") or "").strip()
        if isinstance(pending_followup_tool_payload, dict)
        else None
    )
    pending_followup_source = (
        str(pending_followup_tool_payload.get("source") or "").strip()
        if isinstance(pending_followup_tool_payload, dict)
        else ""
    )
    pending_followup_intent = _get_pending_followup_intent(session, now_ts)
    is_short_followup = bool(not required_tool and _is_short_context_followup(effective_content))
    is_short_confirmation = bool(not required_tool and _looks_like_short_confirmation(effective_content))
    if (
        not required_tool
        and str(decision.profile).upper() == "RESEARCH"
        and _tool_registry_has(loop, "web_search")
        and _looks_like_live_research_query(effective_content)
    ):
        required_tool = "web_search"
        required_tool_query = effective_content
        decision.is_complex = True
        logger.info(
            f"Research safety latch: '{_normalize_text(effective_content)[:120]}' -> required_tool=web_search"
        )
        fast_direct_context = bool(
            perf_cfg
            and bool(getattr(perf_cfg, "fast_first_response", True))
            and required_tool in direct_tools
        )

    if (
        pending_followup_tool
        and not decision.is_complex
        and not required_tool
        and (is_short_followup or is_short_confirmation)
    ):
        required_tool = pending_followup_tool
        if pending_followup_source:
            required_tool_query = pending_followup_source
        decision.is_complex = True
        logger.info(
            f"Session follow-up inference: '{_normalize_text(effective_content)}' -> required_tool={required_tool}"
        )
        fast_direct_context = bool(
            perf_cfg
            and bool(getattr(perf_cfg, "fast_first_response", True))
            and required_tool in direct_tools
        )

    # Infer required tool for short follow-ups before context building, so
    # confirmations like "gas"/"ambil sekarang" can take the direct fast path.
    if not decision.is_complex and not required_tool:
        normalized_followup = _normalize_text(effective_content)
        if _is_short_context_followup(normalized_followup):
            inferred_tool = None
            inferred_source = None
            infer_from_history = getattr(loop, "_infer_required_tool_from_history", None)
            if callable(infer_from_history):
                try:
                    inferred_tool, inferred_source = infer_from_history(
                        effective_content,
                        conversation_history,
                    )
                except Exception:
                    inferred_tool, inferred_source = None, None
            else:
                # Backward-compatible fallback for lightweight test doubles
                # that don't expose the loop facade helper yet.
                for item in reversed(conversation_history[-8:]):
                    role = str(item.get("role", "") or "").strip().lower()
                    candidate = str(item.get("content", "") or "").strip()
                    if not candidate:
                        continue
                    # Never infer required tools from assistant text. Assistant
                    # summaries/offers can contain rich keywords/tickers that are
                    # not fresh user intent and can cause rigid/hallucinated routing.
                    if role != "user":
                        continue
                    candidate_norm = _normalize_text(candidate)
                    if not candidate_norm or candidate_norm == normalized_followup:
                        continue
                    if _looks_like_short_confirmation(candidate):
                        continue
                    inferred = loop._required_tool_for_query(candidate)
                    if inferred:
                        inferred_tool = inferred
                        inferred_source = candidate
                        break
            if inferred_tool:
                required_tool = inferred_tool
                required_tool_query = str(inferred_source or required_tool_query or effective_content).strip()
                decision.is_complex = True
                logger.info(
                    f"Pre-context follow-up inference: '{normalized_followup}' -> required_tool={inferred_tool}"
                )
                fast_direct_context = bool(
                    perf_cfg
                    and bool(getattr(perf_cfg, "fast_first_response", True))
                    and required_tool in direct_tools
                )

    if (
        pending_followup_intent
        and not required_tool
        and (is_short_followup or is_short_confirmation)
    ):
        intent_text = str(pending_followup_intent.get("text") or "").strip()
        intent_profile = str(pending_followup_intent.get("profile") or "GENERAL").strip().upper()
        inferred_tool = loop._required_tool_for_query(intent_text) if intent_text else None
        if inferred_tool:
            required_tool = inferred_tool
            required_tool_query = intent_text
            decision.is_complex = True
            logger.info(
                f"Session intent follow-up inference: '{_normalize_text(effective_content)}' -> required_tool={inferred_tool}"
            )
            fast_direct_context = bool(
                perf_cfg
                and bool(getattr(perf_cfg, "fast_first_response", True))
                and required_tool in direct_tools
            )
        else:
            # Preserve non-tool intent context so short confirms like
            # "ya/lanjut/gas" still continue the previous actionable flow.
            effective_content = (
                f"{effective_content}\n\n[Follow-up Context]\n{intent_text}"
                if intent_text
                else effective_content
            )
            if not decision.is_complex and str(decision.profile).upper() == "CHAT":
                decision.profile = intent_profile if intent_profile else decision.profile
                if intent_profile in {"CODING", "RESEARCH", "GENERAL"}:
                    decision.is_complex = True
            logger.info(
                f"Session intent context continued: '{_normalize_text(effective_content)[:120]}' profile={decision.profile} complex={decision.is_complex}"
            )

    if required_tool:
        _set_pending_followup_tool(session, required_tool, now_ts, str(required_tool_query or effective_content))
    elif not is_short_followup and not is_short_confirmation:
        _clear_pending_followup_tool(session)

    if _should_store_followup_intent(
        intent_source_for_followup,
        required_tool=required_tool,
        decision_profile=str(decision.profile),
        decision_is_complex=bool(decision.is_complex),
    ):
        _set_pending_followup_intent(session, intent_source_for_followup, str(decision.profile), now_ts)
    elif not _is_short_context_followup(intent_source_for_followup) and not _looks_like_short_confirmation(intent_source_for_followup):
        _clear_pending_followup_intent(session)

    runtime_locale = _resolve_runtime_locale(session, msg, effective_content)
    if isinstance(msg.metadata, dict):
        msg.metadata["runtime_locale"] = runtime_locale
        msg.metadata["effective_content"] = effective_content
        if required_tool:
            msg.metadata["required_tool"] = required_tool
            msg.metadata["required_tool_query"] = str(required_tool_query or effective_content).strip()
        else:
            msg.metadata.pop("required_tool", None)
            msg.metadata.pop("required_tool_query", None)
        msg.metadata["skip_critic_for_speed"] = bool(
            required_tool
            or _is_short_context_followup(msg.content)
            or _is_short_context_followup(effective_content)
            or _looks_like_short_confirmation(msg.content)
            or _looks_like_short_confirmation(effective_content)
        )
        msg.metadata["status_mutable_lane"] = bool(
            _channel_uses_mutable_status_lane(loop, msg.channel)
        )

    fast_simple_context = bool(
        perf_cfg
        and bool(getattr(perf_cfg, "fast_first_response", True))
        and not decision.is_complex
        and not required_tool
    )

    queue_meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    queue_info = queue_meta.get("queue") if isinstance(queue_meta.get("queue"), dict) else {}
    dropped_count = int(queue_info.get("dropped_count", 0) or 0)
    dropped_preview = queue_info.get("dropped_preview", [])
    preview_items = [str(item).strip() for item in dropped_preview if str(item).strip()]
    untrusted_context = _build_untrusted_context_payload(
        msg,
        dropped_count=dropped_count,
        dropped_preview=preview_items,
    )

    queued_status = t("runtime.status.queued", locale=runtime_locale, text=effective_content)
    if dropped_count > 0:
        queued_status += " " + t(
            "runtime.status.queued_merged",
            locale=runtime_locale,
            text=effective_content,
            count=dropped_count,
        )
        merge_note = f"[Queue Merge] {dropped_count} pending message(s) were merged before processing."
        if preview_items:
            merge_note += " Earlier snippets: " + " | ".join(preview_items[:2])
        effective_content = f"{effective_content}\n\n{merge_note}"
    thinking_status = t("runtime.status.thinking", locale=runtime_locale, text=effective_content)
    done_status = t("runtime.status.done", locale=runtime_locale, text=effective_content)
    error_status = t("runtime.status.error", locale=runtime_locale, text=effective_content)

    async def _publish_status(text: str, phase: str, *, keepalive: bool = False) -> None:
        bus = getattr(loop, "bus", None)
        publish = getattr(bus, "publish_outbound", None)
        if not callable(publish):
            return
        try:
            metadata = {"type": "status_update", "phase": phase}
            metadata["lane"] = "status"
            if keepalive:
                metadata["keepalive"] = True
            await publish(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=text,
                    metadata=metadata,
                )
            )
        except Exception:
            return

    keepalive_stop = asyncio.Event()
    keepalive_task: asyncio.Task | None = None

    async def _keepalive_loop() -> None:
        try:
            try:
                await asyncio.wait_for(
                    keepalive_stop.wait(),
                    timeout=float(_KEEPALIVE_INITIAL_DELAY_SECONDS),
                )
                return
            except asyncio.TimeoutError:
                pass

            while not keepalive_stop.is_set():
                await _publish_status(thinking_status, "thinking", keepalive=True)
                try:
                    await asyncio.wait_for(
                        keepalive_stop.wait(),
                        timeout=float(_KEEPALIVE_INTERVAL_SECONDS),
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            return

    mutable_status_lane = bool(_channel_uses_mutable_status_lane(loop, msg.channel))
    keepalive_enabled = bool(
        not is_background_task and _channel_supports_keepalive_passthrough(loop, msg.channel)
    )
    if not is_background_task:
        await _publish_status(queued_status, "queued")
        if keepalive_enabled and isinstance(msg.metadata, dict):
            msg.metadata["suppress_initial_thinking_status"] = True
        if keepalive_enabled:
            keepalive_task = asyncio.create_task(_keepalive_loop())
    try:
        context_builder = loop.context
        resolve_context = getattr(loop, "_resolve_context_for_message", None)
        if callable(resolve_context):
            try:
                resolved_context = resolve_context(msg)
                if resolved_context is not None:
                    context_builder = resolved_context
            except Exception as exc:
                logger.warning(f"Failed to resolve routed context builder: {exc}")

        if fast_direct_context or fast_simple_context:
            messages = [{"role": "user", "content": effective_content}]
            context_build_ms = 0
        else:
            context_started = time.perf_counter()
            messages = await asyncio.to_thread(
                context_builder.build_messages,
                history=conversation_history,
                current_message=effective_content,
                media=msg.media if hasattr(msg, "media") else None,
                channel=msg.channel,
                chat_id=msg.chat_id,
                profile=decision.profile,
                tool_names=loop.tools.tool_names,
                untrusted_context=untrusted_context,
            )
            context_build_ms = int((time.perf_counter() - context_started) * 1000)
        max_context_build_ms = int(getattr(perf_cfg, "max_context_build_ms", 500)) if perf_cfg else 500
        logger.info(f"turn_id={turn_id} context_build_ms={context_build_ms}")
        _emit_runtime_event(
            loop,
            "context_built",
            turn_id=turn_id,
            context_build_ms=context_build_ms,
        )
        if context_build_ms > max_context_build_ms:
            logger.warning(
                f"turn_id={turn_id} context_build_ms={context_build_ms} exceeded budget={max_context_build_ms}"
            )

        if decision.is_complex or required_tool:
            if required_tool and not decision.is_complex:
                logger.info(f"Route override: simple -> complex (required_tool={required_tool})")
            final_content = await loop._run_agent_loop(msg, messages, session)
        else:
            if not is_background_task and mutable_status_lane:
                await _publish_status(thinking_status, "thinking")
            final_content = await loop._run_simple_response(msg, messages)
            if not is_background_task and mutable_status_lane:
                await _publish_status(done_status if final_content else error_status, "done" if final_content else "error")
    finally:
        keepalive_stop.set()
        if keepalive_task is not None:
            keepalive_task.cancel()
            with suppress(asyncio.CancelledError):
                await keepalive_task

    first_response_ms = int((time.perf_counter() - turn_started) * 1000)
    logger.info(f"turn_id={turn_id} first_response_ms={first_response_ms}")
    warmup_ms: int | None = None
    started_at = getattr(loop, "_memory_warmup_started_at", None)
    completed_at = getattr(loop, "_memory_warmup_completed_at", None)
    if isinstance(started_at, (int, float)) and isinstance(completed_at, (int, float)) and completed_at >= started_at:
        warmup_ms = int((completed_at - started_at) * 1000)
    _emit_runtime_event(
        loop,
        "turn_end",
        turn_id=turn_id,
        first_response_ms=first_response_ms,
        memory_warmup_ms=warmup_ms if warmup_ms is not None else -1,
    )
    max_first_response_soft = int(getattr(perf_cfg, "max_first_response_ms_soft", 4000)) if perf_cfg else 4000
    if first_response_ms > max_first_response_soft:
        logger.warning(
            f"turn_id={turn_id} first_response_ms={first_response_ms} exceeded soft_target={max_first_response_soft}"
        )

    # Start memory warmup after first response path when defer mode is active.
    if perf_cfg and bool(getattr(perf_cfg, "defer_memory_warmup", True)):
        ensure_warmup = getattr(loop, "_ensure_memory_warmup_task", None)
        if callable(ensure_warmup):
            ensure_warmup()

    return await loop._finalize_session(msg, session, final_content)


async def process_pending_exec_approval(
    loop: Any,
    msg: InboundMessage,
    action: str,
    approval_id: str | None = None,
) -> OutboundMessage:
    """Handle explicit approval commands for pending exec actions."""
    session = await loop._init_session(msg)
    exec_tool = loop.tools.get("exec")
    if not exec_tool or not hasattr(exec_tool, "consume_pending_approval"):
        return await loop._finalize_session(
            msg,
            session,
            "No executable approval flow is available in this session.",
        )

    if action == "deny":
        cleared = exec_tool.clear_pending_approval(msg.session_key, approval_id)
        if cleared:
            return await loop._finalize_session(
                msg,
                session,
                "Pending command approval denied.",
            )
        return await loop._finalize_session(
            msg,
            session,
            "No matching pending command approval found.",
        )

    pending = exec_tool.consume_pending_approval(msg.session_key, approval_id)
    if not pending:
        return await loop._finalize_session(
            msg,
            session,
            "No matching pending command approval found.",
        )

    command = pending.get("command")
    if not isinstance(command, str) or not command.strip():
        return await loop._finalize_session(
            msg,
            session,
            "Pending approval entry is invalid.",
        )

    working_dir = pending.get("working_dir")
    result = await exec_tool.execute(
        command=command,
        working_dir=working_dir if isinstance(working_dir, str) else None,
        _session_key=msg.session_key,
        _approved_by_user=True,
    )
    return await loop._finalize_session(msg, session, result)


async def process_system_message(loop: Any, msg: InboundMessage) -> OutboundMessage | None:
    """Process synthetic/system messages (e.g., cron callbacks)."""
    logger.info(f"Processing system message from {msg.sender_id}")
    if ":" in msg.chat_id:
        parts = msg.chat_id.split(":", 1)
        origin_channel, origin_chat_id = parts[0], parts[1]
    else:
        origin_channel, origin_chat_id = "cli", msg.chat_id

    session_key = f"{origin_channel}:{origin_chat_id}"
    session = loop.sessions.get_or_create(session_key)

    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(origin_channel, origin_chat_id)

    context_builder = loop.context
    resolve_context = getattr(loop, "_resolve_context_for_channel_chat", None)
    if callable(resolve_context):
        try:
            resolved_context = resolve_context(origin_channel, origin_chat_id)
            if resolved_context is not None:
                context_builder = resolved_context
        except Exception as exc:
            logger.warning(f"Failed to resolve system routed context builder: {exc}")

    messages = context_builder.build_messages(
        history=session.get_history(),
        current_message=msg.content,
        channel=origin_channel,
        chat_id=origin_chat_id,
    )

    final_content = await loop._run_agent_loop(msg, messages, session)
    session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
    if final_content:
        session.add_message("assistant", final_content)
    try:
        loop.sessions.save(session)
    except Exception as exc:
        logger.warning(f"Session save failed for {session_key}: {exc}")
    return OutboundMessage(
        channel=origin_channel,
        chat_id=origin_chat_id,
        content=final_content or "",
    )


async def process_isolated(
    loop: Any,
    content: str,
    channel: str = "cli",
    chat_id: str = "direct",
    job_id: str = "",
) -> str:
    """Process a message in a fully isolated session."""
    session_key = f"isolated:cron:{job_id}" if job_id else f"isolated:{int(time.time())}"
    msg = InboundMessage(
        channel=channel,
        sender_id="system",
        chat_id=chat_id,
        content=content,
        _session_key=session_key,
    )

    # Set context for tools without loading history
    for tool_name in ["message", "spawn", "cron"]:
        tool = loop.tools.get(tool_name)
        if hasattr(tool, "set_context"):
            tool.set_context(channel, chat_id)

    # Build messages without history: fresh context
    context_builder = loop.context
    resolve_context = getattr(loop, "_resolve_context_for_channel_chat", None)
    if callable(resolve_context):
        try:
            resolved_context = resolve_context(channel, chat_id)
            if resolved_context is not None:
                context_builder = resolved_context
        except Exception as exc:
            logger.warning(f"Failed to resolve isolated routed context builder: {exc}")

    messages = context_builder.build_messages(
        history=[],
        current_message=content,
        channel=channel,
        chat_id=chat_id,
        profile="GENERAL",
        tool_names=loop.tools.tool_names,
    )

    # Create a minimal session for isolated execution
    session = loop.sessions.get_or_create(session_key)

    # Run the full loop for isolated jobs.
    final_content = await loop._run_agent_loop(msg, messages, session)
    return final_content or ""
