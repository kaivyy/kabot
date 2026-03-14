"""Directive parsing, persistence, and runtime overrides."""

from __future__ import annotations

from typing import Any

from loguru import logger

from kabot.core.directives import DirectiveSet


def parse_directives(loop: Any, message: str) -> tuple[str, DirectiveSet]:
    parser = getattr(loop, "directive_parser", None)
    if parser is None or not hasattr(parser, "parse"):
        return str(message or ""), DirectiveSet()
    clean_body, directives = parser.parse(message)
    return str(clean_body or ""), directives


def format_active_directives(loop: Any, directives: DirectiveSet) -> str:
    parser = getattr(loop, "directive_parser", None)
    if parser is not None and hasattr(parser, "format_active_directives"):
        try:
            return str(parser.format_active_directives(directives) or "").strip()
        except Exception as exc:
            logger.debug(f"Directive formatting skipped: {exc}")
    return ""


def directive_state_from_parsed(directives: DirectiveSet) -> dict[str, Any]:
    raw_directives = (
        dict(directives.raw_directives)
        if isinstance(getattr(directives, "raw_directives", None), dict)
        else {}
    )
    if not raw_directives:
        return {}
    return {
        "think": bool(getattr(directives, "think", False)),
        "verbose": bool(getattr(directives, "verbose", False)),
        "elevated": bool(getattr(directives, "elevated", False)),
        "json_output": bool(getattr(directives, "json_output", False)),
        "no_tools": bool(getattr(directives, "no_tools", False)),
        "raw": bool(getattr(directives, "raw", False)),
        "debug": bool(getattr(directives, "debug", False)),
        "model": str(getattr(directives, "model", "") or "").strip() or None,
        "temperature": getattr(directives, "temperature", None),
        "max_tokens": getattr(directives, "max_tokens", None),
        "raw_directives": raw_directives,
    }


def normalize_directive_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    raw_directives = dict(value.get("raw_directives") or {}) if isinstance(value.get("raw_directives"), dict) else {}
    state = {
        "think": bool(value.get("think", False)),
        "verbose": bool(value.get("verbose", False)),
        "elevated": bool(value.get("elevated", False)),
        "json_output": bool(value.get("json_output", False)),
        "no_tools": bool(value.get("no_tools", False)),
        "raw": bool(value.get("raw", False)),
        "debug": bool(value.get("debug", False)),
        "model": str(value.get("model") or "").strip() or None,
        "temperature": value.get("temperature"),
        "max_tokens": value.get("max_tokens"),
        "raw_directives": raw_directives,
    }
    if raw_directives:
        return state
    if any(
        (
            state["think"],
            state["verbose"],
            state["elevated"],
            state["json_output"],
            state["no_tools"],
            state["raw"],
            state["debug"],
            state["model"],
            state["temperature"] is not None,
            state["max_tokens"] is not None,
        )
    ):
        return state
    return {}


def persist_directives(loop: Any, session: Any, directives: DirectiveSet) -> dict[str, Any] | None:
    state = directive_state_from_parsed(directives)
    if not state:
        return None
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    metadata["directives"] = state
    sessions = getattr(loop, "sessions", None)
    if sessions is not None and hasattr(sessions, "save"):
        sessions.save(session)
    return state


def apply_directive_overrides(msg: Any, directives: DirectiveSet) -> None:
    metadata = getattr(msg, "metadata", None)
    if not isinstance(metadata, dict):
        return

    model = str(getattr(directives, "model", "") or "").strip()
    if model:
        metadata["model_override"] = model
        metadata["model_override_source"] = "directive"

    temperature = getattr(directives, "temperature", None)
    if isinstance(temperature, (int, float)):
        metadata["directive_temperature"] = float(temperature)

    max_tokens = getattr(directives, "max_tokens", None)
    if isinstance(max_tokens, int):
        metadata["directive_max_tokens"] = max_tokens

    if bool(getattr(directives, "json_output", False)):
        metadata["directive_json_output"] = True
    if bool(getattr(directives, "no_tools", False)):
        metadata["directive_no_tools"] = True
    if bool(getattr(directives, "raw", False)):
        metadata["directive_raw"] = True
    if bool(getattr(directives, "debug", False)):
        metadata["directive_debug"] = True
