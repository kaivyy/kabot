"""Execution loop and tool-call runtime extracted from AgentLoop."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

from kabot.agent.fallback_i18n import t
from kabot.agent.loop_core.execution_runtime_parts.helpers import (
    _apply_channel_tool_result_hard_cap,
    _extract_single_result_path,
    _apply_response_quota_usage,
    _build_pending_interrupt_note,
    _emit_runtime_event,
    _looks_like_live_research_query,
    _looks_like_short_confirmation,
    _prune_expiring_cache,
    _query_has_explicit_payload_for_tool,
    _resolve_query_text_from_message,
    _resolve_expected_tool_for_query,
    _resolve_token_mode,
    _runtime_performance_cfg,
    _runtime_resilience_cfg,
    _sanitize_error,
    _schedule_memory_write,
    _should_defer_memory_write,
    _should_skip_memory_persistence,
    _skill_creation_guard_reason,
    _skill_creation_status_phase,
    _stable_tool_payload_hash,
    _take_pending_interrupt_messages,
    _tool_call_intent_mismatch_reason,
    _update_completion_evidence,
    _update_followup_context_from_tool_execution,
    _verify_completion_artifact_path,
)
from kabot.agent.loop_core.execution_runtime_parts.llm import (
    _active_llm_request_overrides,
    call_llm_with_fallback,
    format_tool_result,
    run_simple_response,
)
from kabot.agent.loop_core.execution_runtime_parts.progress import TurnProgressRuntime
from kabot.agent.loop_core.execution_runtime_parts.tool_processing import (
    _tool_result_continuation_payload,
    _tool_result_fetch_fallback_payload,
    process_tool_calls,
)
from kabot.agent.loop_core.tool_enforcement import (
    _extract_list_dir_limit,
    _extract_list_dir_path,
    _extract_message_delivery_path,
    _extract_read_file_path,
    _looks_like_write_file_request,
    _resolve_delivery_path,
    infer_action_required_tool_for_loop,
)
from kabot.agent.loop_core.tool_enforcement_parts.core import (
    _get_last_navigated_path,
    _get_working_directory,
)
from kabot.bus.events import InboundMessage, OutboundMessage

__all__ = [
    "format_tool_result",
    "call_llm_with_fallback",
    "run_agent_loop",
    "run_simple_response",
    "_apply_response_quota_usage",
    "_resolve_expected_tool_for_query",
    "_sanitize_error",
]


async def run_agent_loop(loop: Any, msg: InboundMessage, messages: list, session: Any) -> str | None:
    """Full planner-executor-critic loop for complex tasks."""
    iteration = 0
    ensure_mcp_tools_loaded = getattr(loop, "_ensure_mcp_tools_loaded", None)
    if callable(ensure_mcp_tools_loaded):
        await ensure_mcp_tools_loaded(msg.session_key)

    message_metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
    models_to_try = loop._resolve_models_for_message(msg)
    model = models_to_try[0]

    self_eval_retried = False
    critic_retried = 0
    max_tool_retry = max(0, int(getattr(_runtime_resilience_cfg(loop), "max_tool_retry_per_turn", 1)))
    tool_enforcement_retries = 0
    immediate_action_retried = False
    grounded_filesystem_inspection_retried = False
    suppress_required_tool_inference = bool(message_metadata.get("suppress_required_tool_inference", False))
    required_tool = None
    raw_user_text = str(msg.content or "").strip()
    raw_user_word_count = len([part for part in raw_user_text.split() if part])
    effective_content = str(message_metadata.get("effective_content") or "").strip()
    question_text = effective_content or raw_user_text
    question_word_count = len([part for part in question_text.split() if part])
    route_profile = str(message_metadata.get("route_profile", "")).strip().upper()
    continuity_source = str(message_metadata.get("continuity_source") or "").strip().lower()
    external_skill_lane = bool(message_metadata.get("external_skill_lane", False))
    requires_real_skill_execution = bool(
        message_metadata.get("requires_real_skill_execution", False)
    )
    requires_grounded_filesystem_inspection = bool(
        message_metadata.get("requires_grounded_filesystem_inspection", False)
    )
    runtime_locale = str(message_metadata.get("runtime_locale") or "").strip() or None
    toolbacked_continuity_sources = {"action_request", "committed_action"}
    coding_execution_continuity_sources = {"coding_request", "committed_coding_action"}
    grounded_filesystem_tools = {"list_dir", "read_file", "find_files", "exec"}
    enforce_toolbacked_action = continuity_source in toolbacked_continuity_sources
    enforce_real_execution = continuity_source in (
        toolbacked_continuity_sources | coding_execution_continuity_sources
    )
    if requires_grounded_filesystem_inspection:
        enforce_real_execution = True
    if requires_real_skill_execution:
        enforce_real_execution = True
    if external_skill_lane and not required_tool and not requires_real_skill_execution:
        enforce_toolbacked_action = False
        enforce_real_execution = False
    coding_execution_context = bool(
        route_profile == "CODING" or continuity_source in coding_execution_continuity_sources
    )
    artifact_verification_retried = False
    delivery_verification_retried = False
    delivery_required = bool(message_metadata.get("requires_message_delivery", False))
    session_metadata = getattr(session, "metadata", None)
    if not isinstance(session_metadata, dict):
        session_metadata = {}
    tools_registry = getattr(loop, "tools", None)
    has_tool = getattr(tools_registry, "has", None)
    resolved_required_tool = str(message_metadata.get("required_tool") or "").strip()
    skill_command_dispatch = str(message_metadata.get("skill_command_dispatch") or "").strip().lower()
    skill_command_tool = str(message_metadata.get("skill_command_tool") or "").strip()
    skill_command_name = str(message_metadata.get("skill_command_name") or "").strip()
    skill_command_arg_mode = str(message_metadata.get("skill_command_arg_mode") or "raw").strip().lower() or "raw"
    if resolved_required_tool:
        if callable(has_tool):
            try:
                if has_tool(resolved_required_tool):
                    required_tool = resolved_required_tool
            except Exception:
                required_tool = resolved_required_tool
        else:
            required_tool = resolved_required_tool
    elif suppress_required_tool_inference:
        required_tool = None
    if (
        not required_tool
        and delivery_required
        and not suppress_required_tool_inference
    ):
        requested_delivery_file = str(_extract_read_file_path(question_text) or "").strip()
        explicit_find_search_request = bool(
            _query_has_explicit_payload_for_tool("find_files", question_text)
            and re.search(r"(?i)\b(find|search|locate|look for)\b", question_text)
        )
        explicit_delivery_action_tool = None
        try:
            explicit_delivery_action_tool, _delivery_action_query = infer_action_required_tool_for_loop(
                loop,
                question_text,
            )
        except Exception:
            explicit_delivery_action_tool = None
        delivery_context_available = bool(
            str(message_metadata.get("working_directory") or session_metadata.get("working_directory") or "").strip()
            or str(message_metadata.get("last_navigated_path") or session_metadata.get("last_navigated_path") or "").strip()
            or isinstance(message_metadata.get("delivery_route"), dict)
            or isinstance(session_metadata.get("delivery_route"), dict)
            or (
                isinstance(message_metadata.get("last_tool_context"), dict)
                and str((message_metadata.get("last_tool_context") or {}).get("path") or "").strip()
            )
            or (
                isinstance(session_metadata.get("last_tool_context"), dict)
                and str((session_metadata.get("last_tool_context") or {}).get("path") or "").strip()
            )
        )
        direct_delivery_candidate = bool(
            requested_delivery_file
            and (
                delivery_context_available
                or bool(re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\|/|~[\\/])", requested_delivery_file))
                or "/" in requested_delivery_file
                or "\\" in requested_delivery_file
            )
        )
        message_payload_available = bool(
            _query_has_explicit_payload_for_tool("message", question_text)
            or direct_delivery_candidate
        )
        if (
            explicit_delivery_action_tool == "find_files"
            or explicit_find_search_request
            or (
                _query_has_explicit_payload_for_tool("find_files", question_text)
                and not delivery_context_available
            )
        ):
            message_tool_available = False
        else:
            message_tool_available = message_payload_available
        if callable(has_tool):
            try:
                message_tool_available = bool(message_tool_available and has_tool("message"))
            except Exception:
                message_tool_available = bool(message_tool_available)
            if message_tool_available:
                required_tool = "message"
                if isinstance(message_metadata, dict):
                    message_metadata.setdefault("required_tool", "message")
                    message_metadata.setdefault("required_tool_query", question_text)
    if skill_command_dispatch == "tool" and skill_command_tool:
        tool_available = True
        if callable(has_tool):
            try:
                tool_available = bool(has_tool(skill_command_tool))
            except Exception:
                tool_available = True
        if not tool_available:
            command_label = f"/{skill_command_name}" if skill_command_name else skill_command_tool
            return (
                f"Skill command {command_label} requires unavailable tool "
                f"'{skill_command_tool}'."
            )
        raw_dispatch_args = str(message_metadata.get("required_tool_query") or question_text or "").strip()
        dispatch_payload = {
            "command": raw_dispatch_args,
            "commandName": skill_command_name or skill_command_tool,
            "skillName": str(message_metadata.get("skill_name") or "").strip(),
        }
        execute_tool = getattr(loop, "_execute_tool", None)
        if callable(execute_tool):
            result = await execute_tool(skill_command_tool, dispatch_payload, session_key=msg.session_key)
        else:
            result = await loop.tools.execute(skill_command_tool, dispatch_payload)
        if isinstance(result, str):
            result_text = result
        else:
            try:
                result_text = json.dumps(result, ensure_ascii=False)
            except Exception:
                result_text = str(result)
        _update_followup_context_from_tool_execution(
            session,
            tool_name=skill_command_tool,
            tool_args=dispatch_payload,
            fallback_source=raw_dispatch_args or raw_user_text,
            tool_result=result_text,
        )
        return result_text
    if enforce_toolbacked_action and not required_tool:
        inferred_action_tool, inferred_action_query = infer_action_required_tool_for_loop(loop, question_text)
        if inferred_action_tool:
            required_tool = inferred_action_tool
            if isinstance(message_metadata, dict):
                message_metadata["required_tool"] = inferred_action_tool
                message_metadata["required_tool_query"] = str(
                    inferred_action_query or question_text
                ).strip()
            logger.info(
                "Execution action-tool inference: "
                f"'{question_text[:120]}' -> required_tool={required_tool}"
            )
    artifact_required_tool = str(required_tool or message_metadata.get("required_tool") or "").strip()
    if not artifact_required_tool and enforce_toolbacked_action:
        inferred_artifact_tool, _ = infer_action_required_tool_for_loop(loop, question_text)
        artifact_required_tool = str(inferred_artifact_tool or "").strip()
    artifact_verification_required = bool(
        enforce_toolbacked_action
        and (
            artifact_required_tool == "write_file"
            or _looks_like_write_file_request(question_text, explicit_path=_extract_read_file_path(question_text))
        )
    )
    explicit_artifact_path = (
        _extract_read_file_path(question_text)
        if artifact_verification_required
        else None
    )

    def _resolve_expected_artifact_path() -> Path | None:
        candidate = str(explicit_artifact_path or "").strip()
        if not candidate:
            return None
        try:
            candidate_path = Path(candidate).expanduser()
            if candidate_path.is_absolute():
                return candidate_path.resolve()
            workspace = getattr(loop, "workspace", None)
            if isinstance(workspace, Path):
                return (workspace / candidate_path).resolve()
            if isinstance(workspace, str) and str(workspace).strip():
                return (Path(workspace).expanduser() / candidate_path).resolve()
            return candidate_path.resolve()
        except Exception:
            return None

    expected_artifact_path = _resolve_expected_artifact_path()

    def _session_last_tool_context() -> dict[str, Any]:
        session_metadata = getattr(session, "metadata", None)
        last_tool_context = (
            session_metadata.get("last_tool_context")
            if isinstance(session_metadata, dict)
            else {}
        )
        return last_tool_context if isinstance(last_tool_context, dict) else {}

    def _message_last_tool_context() -> dict[str, Any]:
        last_tool_context = (
            message_metadata.get("last_tool_context")
            if isinstance(message_metadata.get("last_tool_context"), dict)
            else {}
        )
        return last_tool_context if isinstance(last_tool_context, dict) else {}

    def _resolve_delivery_candidate_path() -> str:
        last_tool_context = _message_last_tool_context() or _session_last_tool_context()
        if not isinstance(last_tool_context, dict):
            last_tool_context = {}
        working_directory = _get_working_directory(loop, msg, message_metadata)
        last_navigated_path = _get_last_navigated_path(loop, msg, message_metadata)

        context_path = str(last_tool_context.get("path") or "").strip()
        context_path_exists = False
        if context_path:
            try:
                context_path_exists = Path(context_path).expanduser().resolve().exists()
            except Exception:
                context_path_exists = False
        fallback_directory = working_directory or last_navigated_path
        if not context_path_exists and fallback_directory:
            last_tool_context = {
                **last_tool_context,
                "tool": str(last_tool_context.get("tool") or "list_dir").strip() or "list_dir",
                "path": fallback_directory,
            }
        candidate = _extract_message_delivery_path(
            question_text,
            last_tool_context=last_tool_context,
        )
        requested_file = str(_extract_read_file_path(question_text) or "").strip()
        if candidate and requested_file:
            try:
                candidate_obj = Path(str(candidate)).expanduser().resolve()
            except Exception:
                candidate_obj = None
            if (
                candidate_obj is not None
                and (
                    (candidate_obj.exists() and candidate_obj.is_dir())
                    or not candidate_obj.suffix
                )
                and not re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\|/|~[\\/])", requested_file)
                and "/" not in requested_file
                and "\\" not in requested_file
            ):
                file_candidate = (candidate_obj / requested_file).resolve()
                if file_candidate.exists() and file_candidate.is_file():
                    return str(file_candidate)
        if requested_file and fallback_directory:
            try:
                nav_base = Path(fallback_directory).expanduser().resolve()
            except Exception:
                nav_base = None
            if (
                nav_base is not None
                and nav_base.exists()
                and nav_base.is_dir()
                and not re.match(r"(?i)^(?:[a-z]:[\\/]|\\\\|/|~[\\/])", requested_file)
                and "/" not in requested_file
                and "\\" not in requested_file
            ):
                candidate_path = (nav_base / requested_file).resolve()
                if candidate_path.exists() and candidate_path.is_file():
                    return str(candidate_path)
        if not candidate:
            return ""
        return str(_resolve_delivery_path(loop, candidate))

    def _record_executed_tool_name(tool_name: str) -> None:
        if not isinstance(message_metadata, dict):
            return
        executed_tools = message_metadata.get("executed_tools")
        if not isinstance(executed_tools, list):
            executed_tools = []
        if tool_name not in executed_tools:
            executed_tools.append(tool_name)
        message_metadata["executed_tools"] = executed_tools

    def _path_looks_like_file(path: str, *, tool_name: str = "") -> bool:
        raw = str(path or "").strip()
        if not raw:
            return False
        if str(tool_name or "").strip().lower() == "read_file":
            return True
        try:
            candidate = Path(raw).expanduser()
            if candidate.suffix:
                return True
        except Exception:
            pass
        filename = raw.replace("\\", "/").rstrip("/").split("/")[-1]
        return "." in filename and not filename.startswith(".")

    def _resolve_grounded_inspection_root() -> str:
        explicit_file_path = str(_extract_read_file_path(question_text) or "").strip()
        if explicit_file_path:
            try:
                explicit_candidate = Path(explicit_file_path).expanduser().resolve()
                if explicit_candidate.exists() and explicit_candidate.is_file():
                    return str(explicit_candidate.parent)
                if explicit_candidate.suffix:
                    return str(explicit_candidate.parent)
            except Exception:
                pass

        last_tool_context = _message_last_tool_context() or _session_last_tool_context()
        explicit_dir_path = _extract_list_dir_path(
            question_text,
            last_tool_context=last_tool_context if isinstance(last_tool_context, dict) else None,
        )
        if explicit_dir_path:
            return str(_resolve_delivery_path(loop, explicit_dir_path))

        candidate_roots = [
            str(message_metadata.get("working_directory") or "").strip(),
        ]
        session_metadata = getattr(session, "metadata", None)
        if isinstance(session_metadata, dict):
            candidate_roots.append(str(session_metadata.get("working_directory") or "").strip())
        if isinstance(last_tool_context, dict):
            tool_name = str(last_tool_context.get("tool") or "").strip()
            path_hint = str(last_tool_context.get("path") or "").strip()
            if path_hint:
                if _path_looks_like_file(path_hint, tool_name=tool_name):
                    try:
                        candidate_roots.append(str(Path(path_hint).expanduser().resolve().parent))
                    except Exception:
                        pass
                else:
                    candidate_roots.append(path_hint)

        workspace = getattr(loop, "workspace", None)
        if isinstance(workspace, Path):
            candidate_roots.append(str(workspace.expanduser().resolve()))
        elif isinstance(workspace, str) and str(workspace).strip():
            try:
                candidate_roots.append(str(Path(workspace).expanduser().resolve()))
            except Exception:
                candidate_roots.append(str(workspace).strip())

        for candidate in candidate_roots:
            raw = str(candidate or "").strip()
            if not raw:
                continue
            try:
                resolved = Path(raw).expanduser().resolve()
            except Exception:
                continue
            if resolved.exists():
                if resolved.is_file():
                    return str(resolved.parent)
                if resolved.is_dir():
                    return str(resolved)

        return ""

    def _parse_list_dir_entry_names(raw_listing: str) -> tuple[list[str], list[str]]:
        files: list[str] = []
        directories: list[str] = []
        for line in str(raw_listing or "").splitlines():
            stripped = str(line or "").strip()
            if stripped.startswith("📄 "):
                files.append(stripped[2:].strip())
            elif stripped.startswith("📁 "):
                directories.append(stripped[2:].strip())
        return files, directories

    def _select_representative_inspection_files(root: str, raw_listing: str) -> list[str]:
        if not root:
            return []
        root_path = Path(root).expanduser()
        files, _directories = _parse_list_dir_entry_names(raw_listing)
        if not files:
            return []
        preferred_names = (
            "README.md",
            "README",
            "README.txt",
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "composer.json",
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "mkdocs.yml",
            "config.json",
            "config.yaml",
            "config.yml",
            "settings.json",
            "AGENTS.md",
            "TOOLS.md",
            "USER.md",
            "BOOTSTRAP.md",
            "CHANGELOG.md",
            "CLAUDE.md",
        )
        chosen: list[str] = []
        seen: set[str] = set()
        lower_to_original = {name.lower(): name for name in files}
        for preferred_name in preferred_names:
            original = lower_to_original.get(preferred_name.lower())
            if not original:
                continue
            candidate = str((root_path / original).expanduser())
            if candidate not in seen:
                seen.add(candidate)
                chosen.append(candidate)
            if len(chosen) >= 3:
                return chosen
        for fallback_name in files:
            candidate = str((root_path / fallback_name).expanduser())
            if candidate in seen:
                continue
            seen.add(candidate)
            chosen.append(candidate)
            if len(chosen) >= 3:
                break
        return chosen

    def _truncate_inspection_text(value: Any, *, limit: int = 2500) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    async def _execute_grounded_inspection_tool(tool_name: str, payload: dict[str, Any]) -> Any:
        execute_tool = getattr(loop, "_execute_tool", None)
        if callable(execute_tool):
            return await execute_tool(tool_name, payload, session_key=msg.session_key)
        return await loop.tools.execute(tool_name, payload)

    def _should_summarize_raw_direct_result(tool_name: str, result_text: str) -> bool:
        if not result_text:
            return False
        normalized = str(result_text or "").strip().lower()
        if not normalized:
            return False
        if tool_name in {"list_dir", "read_file", "find_files", "message"}:
            humanized_error_prefixes = (
                "i couldn't find that file yet:",
                "i couldn't find that folder yet:",
                "aku belum menemukan file ini:",
                "aku belum menemukan folder ini:",
                "saya belum menjumpai fail ini:",
                "saya belum menjumpai folder ini:",
                "not a file:",
                "not a directory:",
                "path ini bukan file:",
                "path ini bukan folder:",
                "laluan ini bukan fail:",
                "laluan ini bukan folder:",
                "permission denied:",
                "akses ditolak:",
                "failed to read file:",
                "gagal membaca file:",
                "gagal memaparkan kandungan folder:",
                "gagal menampilkan isi folder:",
            )
            return normalized.startswith(humanized_error_prefixes)
        return False
    # Fast-turn responsiveness: skip expensive critic retries for short/chat/required-tool turns.
    skip_critic_for_speed = (
        bool(message_metadata.get("skip_critic_for_speed", False))
        or
        bool(required_tool)
        or (raw_user_word_count <= 12 and not coding_execution_context)
        or (question_word_count <= 10 and not coding_execution_context)
        or (_looks_like_short_confirmation(raw_user_text) and not coding_execution_context)
        or (_looks_like_short_confirmation(question_text) and not coding_execution_context)
        or (_looks_like_live_research_query(raw_user_text) and not coding_execution_context)
        or ("[follow-up context]" in question_text.lower() and not coding_execution_context)
        or route_profile in {"CHAT", "RESEARCH"}
    )
    is_background_task = (
        (msg.channel or "").lower() == "system"
        or (msg.sender_id or "").lower() == "system"
        or (
            isinstance(msg.content, str)
            and msg.content.strip().lower().startswith("heartbeat task:")
        )
    )
    # Synthetic/system callbacks (cron completion, heartbeat, etc.) should not
    # trigger hard tool-enforcement loops from reminder/weather keywords inside
    # system-generated text.
    if is_background_task:
        required_tool = None
    tools_executed = False

    is_weak_model_fn = getattr(loop, "_is_weak_model", None)
    if callable(is_weak_model_fn):
        try:
            is_weak_model = bool(is_weak_model_fn(model))
        except Exception:
            is_weak_model = False
    else:
        is_weak_model = False
    max_critic_retries = 1 if is_weak_model else 2
    critic_threshold = 5 if is_weak_model else 7

    first_score = None
    skill_creation_phase = _skill_creation_status_phase(message_metadata)
    progress_runtime = TurnProgressRuntime(
        loop=loop,
        msg=msg,
        session=session,
        message_metadata=message_metadata,
        runtime_locale=runtime_locale,
        question_text=question_text,
        is_background_task=is_background_task,
        skill_creation_phase=skill_creation_phase,
    )

    await progress_runtime.publish_phase(skill_creation_phase or "thinking")

    if (
        requires_grounded_filesystem_inspection
        and not required_tool
        and not is_background_task
    ):
        inspection_root = _resolve_grounded_inspection_root()
        list_dir_available = True
        read_file_available = True
        if callable(has_tool):
            try:
                list_dir_available = bool(has_tool("list_dir"))
            except Exception:
                list_dir_available = True
            try:
                read_file_available = bool(has_tool("read_file"))
            except Exception:
                read_file_available = True
        if inspection_root and list_dir_available:
            await progress_runtime.publish_phase("tool")
            try:
                inspection_listing_result = await _execute_grounded_inspection_tool(
                    "list_dir",
                    {"path": inspection_root, "limit": 80},
                )
            except Exception as exc:
                inspection_listing_result = (
                    f"Grounded inspection warmup failed for {inspection_root}: {exc}"
                )
            inspection_listing_text = str(inspection_listing_result or "").strip()
            if inspection_listing_text:
                tools_executed = True
                _record_executed_tool_name("list_dir")
                _update_followup_context_from_tool_execution(
                    session,
                    tool_name="list_dir",
                    tool_args={"path": inspection_root, "limit": 80},
                    fallback_source=question_text,
                    tool_result=inspection_listing_result,
                )
                inspection_context_blocks = [
                    "[Grounded Inspection Warmup]",
                    f"Inspection root: {inspection_root}",
                    "[Initial Directory Listing]",
                    _truncate_inspection_text(inspection_listing_text, limit=2400),
                ]
                representative_paths = (
                    _select_representative_inspection_files(inspection_root, inspection_listing_text)
                    if read_file_available
                    else []
                )
                for representative_path in representative_paths:
                    try:
                        representative_result = await _execute_grounded_inspection_tool(
                            "read_file",
                            {"path": representative_path},
                        )
                    except Exception as exc:
                        representative_result = f"Failed to read {representative_path}: {exc}"
                    representative_text = str(representative_result or "").strip()
                    if not representative_text:
                        continue
                    tools_executed = True
                    _record_executed_tool_name("read_file")
                    _update_followup_context_from_tool_execution(
                        session,
                        tool_name="read_file",
                        tool_args={"path": representative_path},
                        fallback_source=question_text,
                        tool_result=representative_result,
                    )
                    inspection_context_blocks.extend(
                        (
                            f"[Representative File: {Path(representative_path).name}]",
                            _truncate_inspection_text(representative_text, limit=2000),
                        )
                    )
                inspection_context_blocks.extend(
                    (
                        "[Inspection Note]",
                        "Use the real filesystem evidence above when answering what this local folder, repo, app, config, or docs say.",
                        "If the evidence is still insufficient, inspect more representative files before concluding.",
                    )
                )
                messages = [
                    *messages,
                    {"role": "user", "content": "\n".join(inspection_context_blocks)},
                ]

    # === FAST PATH: Execute deterministic tools directly, skip LLM tool-call step ===
    # This bypasses fragile tool-call protocols for deterministic intents.
    direct_tools = {
        "find_files",
        "read_file",
        "write_file",
        "archive_path",
        "list_dir",
        "message",
        "save_memory",
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
        "image_gen",
    }
    raw_direct_tools = {
        "find_files",
        "read_file",
        "write_file",
        "archive_path",
        "list_dir",
        "message",
        "cleanup_system",
        "get_process_memory",
        "web_search",
        "check_update",
        "system_update",
        "weather",
        "stock",
        "crypto",
        "image_gen",
    }
    if (
        not required_tool
        and delivery_required
        and callable(has_tool)
        and has_tool("find_files")
        and has_tool("message")
        and _query_has_explicit_payload_for_tool("find_files", question_text)
    ):
        await progress_runtime.publish_phase("tool")
        find_result = await loop._execute_required_tool_fallback("find_files", msg)
        if find_result is not None:
            logger.info("Direct workflow execution (bypassed LLM tool-call): find_files -> message")
            source_hint = str(message_metadata.get("required_tool_query") or "").strip()
            if not source_hint:
                source_hint = _resolve_query_text_from_message(msg)
            _update_followup_context_from_tool_execution(
                session,
                tool_name="find_files",
                tool_args={},
                fallback_source=source_hint,
                tool_result=find_result,
            )
            if isinstance(message_metadata, dict):
                executed_tools = message_metadata.get("executed_tools")
                if not isinstance(executed_tools, list):
                    executed_tools = []
                if "find_files" not in executed_tools:
                    executed_tools.append("find_files")
                message_metadata["executed_tools"] = executed_tools
                session_metadata = getattr(session, "metadata", None)
                if isinstance(session_metadata, dict):
                    last_tool_context = session_metadata.get("last_tool_context")
                    if isinstance(last_tool_context, dict):
                        message_metadata["last_tool_context"] = dict(last_tool_context)

            matched_path = _extract_single_result_path("find_files", {}, find_result)
            if matched_path:
                first_match_kind = ""
                for line in str(find_result or "").splitlines():
                    stripped = str(line or "").strip()
                    if stripped.startswith("FILE ") or stripped.startswith("DIR "):
                        first_match_kind = "dir" if stripped.startswith("DIR ") else "file"
                        break
                delivery_path = matched_path
                if isinstance(message_metadata, dict):
                    last_tool_context = message_metadata.get("last_tool_context")
                    if not isinstance(last_tool_context, dict):
                        last_tool_context = {"tool": "find_files", "source": source_hint}
                    last_tool_context["path"] = matched_path
                    message_metadata["last_tool_context"] = last_tool_context
                if (
                    first_match_kind == "dir"
                    and callable(has_tool)
                    and has_tool("archive_path")
                ):
                    archive_result = await loop._execute_required_tool_fallback("archive_path", msg)
                    archive_text = str(archive_result or "").strip()
                    if archive_text:
                        archive_path = _extract_single_result_path("archive_path", {}, archive_result)
                        _update_followup_context_from_tool_execution(
                            session,
                            tool_name="archive_path",
                            tool_args={"path": matched_path},
                            fallback_source=source_hint,
                            tool_result=archive_result,
                        )
                        if isinstance(message_metadata, dict):
                            executed_tools = message_metadata.get("executed_tools")
                            if not isinstance(executed_tools, list):
                                executed_tools = []
                            if "archive_path" not in executed_tools:
                                executed_tools.append("archive_path")
                            message_metadata["executed_tools"] = executed_tools
                        if archive_path:
                            delivery_path = archive_path
                            if isinstance(message_metadata, dict):
                                last_tool_context = message_metadata.get("last_tool_context")
                                if not isinstance(last_tool_context, dict):
                                    last_tool_context = {"tool": "archive_path", "source": source_hint}
                                last_tool_context["path"] = archive_path
                                message_metadata["last_tool_context"] = last_tool_context
                        else:
                            return await progress_runtime.return_with_phase(archive_text)
                verified_delivery_path, delivery_artifact_exists = _verify_completion_artifact_path(
                    loop,
                    delivery_path,
                )
                _update_completion_evidence(
                    message_metadata,
                    session,
                    artifact_paths=[verified_delivery_path] if verified_delivery_path else None,
                    artifact_verified=delivery_artifact_exists,
                    delivery_verified=False,
                )
                if not delivery_artifact_exists:
                    return await progress_runtime.return_with_phase(
                        "I couldn't verify the requested artifact because the target file still "
                        "does not exist. I won't claim the task is done without filesystem evidence.",
                        phase="error",
                    )
                message_result = await loop._execute_required_tool_fallback("message", msg)
                message_text = str(message_result or "").strip()
                if message_text:
                    _update_followup_context_from_tool_execution(
                        session,
                        tool_name="message",
                        tool_args={"files": [delivery_path]},
                        fallback_source=source_hint,
                        tool_result=message_text,
                    )
                    if isinstance(message_metadata, dict):
                        executed_tools = message_metadata.get("executed_tools")
                        if not isinstance(executed_tools, list):
                            executed_tools = []
                        if "message" not in executed_tools:
                            executed_tools.append("message")
                        message_metadata["executed_tools"] = executed_tools
                        if message_text.lower().startswith("message sent to "):
                            message_metadata["message_delivery_verified"] = True
                    _update_completion_evidence(
                        message_metadata,
                        session,
                        artifact_paths=[verified_delivery_path] if verified_delivery_path else None,
                        artifact_verified=delivery_artifact_exists,
                        delivery_paths=[verified_delivery_path] if verified_delivery_path else None,
                        delivery_verified=message_text.lower().startswith("message sent to "),
                    )
                    return await progress_runtime.return_with_phase(message_text)
            return await progress_runtime.return_with_phase(str(find_result))
    if required_tool and required_tool in direct_tools:
        await progress_runtime.publish_phase("tool")
        direct_result = await loop._execute_required_tool_fallback(required_tool, msg)
        if direct_result is not None:
            logger.info(f"Direct tool execution (bypassed LLM tool-call): {required_tool}")
            source_hint = str(message_metadata.get("required_tool_query") or "").strip()
            if not source_hint:
                source_hint = _resolve_query_text_from_message(msg)
            direct_tool_args: dict[str, Any] = {}
            if required_tool == "web_search" and source_hint:
                direct_tool_args["query"] = source_hint
            if required_tool == "write_file" and explicit_artifact_path:
                direct_tool_args["path"] = explicit_artifact_path
            if required_tool == "list_dir":
                list_dir_context = _message_last_tool_context() or _session_last_tool_context()
                list_dir_path = _extract_list_dir_path(
                    source_hint or question_text,
                    last_tool_context=list_dir_context,
                )
                if list_dir_path:
                    direct_tool_args["path"] = list_dir_path
                list_dir_limit = _extract_list_dir_limit(source_hint or question_text)
                if list_dir_limit is not None:
                    direct_tool_args["limit"] = list_dir_limit
            if required_tool == "message":
                delivery_candidate_path = _resolve_delivery_candidate_path()
                if delivery_candidate_path:
                    direct_tool_args["files"] = [delivery_candidate_path]
            _update_followup_context_from_tool_execution(
                session,
                tool_name=required_tool,
                tool_args=direct_tool_args,
                fallback_source=source_hint,
                tool_result=direct_result,
            )
            if isinstance(message_metadata, dict):
                executed_tools = message_metadata.get("executed_tools")
                if not isinstance(executed_tools, list):
                    executed_tools = []
                if required_tool not in executed_tools:
                    executed_tools.append(required_tool)
                message_metadata["executed_tools"] = executed_tools
            continue_after_direct_tool = False
            if required_tool == "web_search":
                passthrough_payload = _tool_result_fetch_fallback_payload(
                    msg,
                    required_tool,
                    direct_tool_args,
                    str(direct_result or ""),
                    tool_call_count=1,
                )
                passthrough_execute_tool = str(
                    (passthrough_payload or {}).get("execute_tool") or ""
                ).strip()
                if passthrough_execute_tool:
                    passthrough_args = passthrough_payload.get("arguments") or {}
                    passthrough_result = await _execute_grounded_inspection_tool(
                        passthrough_execute_tool,
                        passthrough_args,
                    )
                    _update_followup_context_from_tool_execution(
                        session,
                        tool_name=passthrough_execute_tool,
                        tool_args=passthrough_args,
                        fallback_source=source_hint,
                        tool_result=passthrough_result,
                    )
                    if isinstance(message_metadata, dict):
                        executed_tools = message_metadata.get("executed_tools")
                        if not isinstance(executed_tools, list):
                            executed_tools = []
                        if passthrough_execute_tool not in executed_tools:
                            executed_tools.append(passthrough_execute_tool)
                        message_metadata["executed_tools"] = executed_tools
                    return await progress_runtime.return_with_phase(
                        str(passthrough_result or "").strip(),
                        phase=str(passthrough_payload.get("phase") or "tool").strip() or "tool",
                    )
                continuation_payload = _tool_result_continuation_payload(
                    loop,
                    msg,
                    session,
                    required_tool,
                    direct_tool_args,
                    str(direct_result or ""),
                    tool_call_count=1,
                )
                if isinstance(continuation_payload, dict) and bool(continuation_payload.get("continue_loop")):
                    continuation_message = str(continuation_payload.get("append_message") or "").strip()
                    if continuation_message:
                        messages.append({"role": "user", "content": continuation_message})
                    if isinstance(message_metadata, dict):
                        message_metadata["suppress_required_tool_inference"] = True
                    required_tool = None
                    tool_enforcement_retries = 0
                    continue_after_direct_tool = True
                    logger.info(
                        "Web-search setup fallback: continuing without search setup prompt "
                        f"for '{_resolve_query_text_from_message(msg)[:120]}'"
                    )
            if not continue_after_direct_tool:
                direct_artifact_path = _extract_single_result_path(required_tool, direct_tool_args, direct_result)
                verified_artifact_path = ""
                artifact_exists = False
                if direct_artifact_path:
                    verified_artifact_path, artifact_exists = _verify_completion_artifact_path(
                        loop,
                        direct_artifact_path,
                    )
                if required_tool == "message" and not verified_artifact_path:
                    delivery_candidate_path = _resolve_delivery_candidate_path()
                    if delivery_candidate_path:
                        verified_artifact_path, artifact_exists = _verify_completion_artifact_path(
                            loop,
                            delivery_candidate_path,
                        )
                direct_delivery_verified = bool(
                    required_tool == "message"
                    and verified_artifact_path
                    and artifact_exists
                    and str(direct_result or "").strip().lower().startswith("message sent to ")
                )
                if required_tool == "message" and isinstance(message_metadata, dict):
                    message_metadata["message_delivery_verified"] = direct_delivery_verified
                _update_completion_evidence(
                    message_metadata,
                    session,
                    artifact_paths=[verified_artifact_path] if verified_artifact_path else None,
                    artifact_verified=artifact_exists if verified_artifact_path else None,
                    delivery_paths=[verified_artifact_path] if direct_delivery_verified else None,
                    delivery_verified=direct_delivery_verified if required_tool == "message" else None,
                )
                if direct_delivery_verified and required_tool == "message":
                    session_metadata = getattr(session, "metadata", None)
                    if isinstance(session_metadata, dict):
                        session_metadata.pop("pending_followup_intent", None)
                        session_metadata.pop("pending_followup_tool", None)
                if (
                    artifact_verification_required
                    and verified_artifact_path
                    and not artifact_exists
                ):
                    return await progress_runtime.return_with_phase(
                        "I couldn't verify the requested artifact because the target file still "
                        "does not exist. I won't claim the task is done without filesystem evidence.",
                        phase="error",
                    )
                if (
                    delivery_required
                    and required_tool != "message"
                    and callable(has_tool)
                    and has_tool("message")
                ):
                    artifact_path = verified_artifact_path or direct_artifact_path
                    if artifact_path and artifact_exists:
                        archive_replaced_directory = False
                        try:
                            resolved_artifact = Path(str(artifact_path)).expanduser().resolve()
                        except Exception:
                            resolved_artifact = None

                        if (
                            resolved_artifact is not None
                            and resolved_artifact.exists()
                            and resolved_artifact.is_dir()
                            and callable(has_tool)
                            and has_tool("archive_path")
                        ):
                            archive_result = await loop._execute_required_tool_fallback("archive_path", msg)
                            archive_text = str(archive_result or "").strip()
                            archive_candidate = _extract_single_result_path(
                                "archive_path",
                                {"path": str(resolved_artifact)},
                                archive_result,
                            )
                            if archive_candidate:
                                verified_archive_path, archive_exists = _verify_completion_artifact_path(
                                    loop,
                                    archive_candidate,
                                )
                                if verified_archive_path and archive_exists:
                                    artifact_path = verified_archive_path
                                    artifact_exists = True
                                    archive_replaced_directory = True
                                    if isinstance(message_metadata, dict):
                                        executed_tools = message_metadata.get("executed_tools")
                                        if not isinstance(executed_tools, list):
                                            executed_tools = []
                                        if "archive_path" not in executed_tools:
                                            executed_tools.append("archive_path")
                                        message_metadata["executed_tools"] = executed_tools
                                    _update_followup_context_from_tool_execution(
                                        session,
                                        tool_name="archive_path",
                                        tool_args={"path": str(resolved_artifact)},
                                        fallback_source=source_hint,
                                        tool_result=archive_text or archive_result,
                                    )
                                elif archive_text:
                                    return await progress_runtime.return_with_phase(archive_text)
                            elif archive_text:
                                return await progress_runtime.return_with_phase(archive_text)

                        if isinstance(message_metadata, dict):
                            last_tool_context = message_metadata.get("last_tool_context")
                            if not isinstance(last_tool_context, dict):
                                last_tool_context = {"tool": required_tool, "source": source_hint}
                            last_tool_context["path"] = artifact_path
                            message_metadata["last_tool_context"] = last_tool_context
                        message_result = await loop._execute_required_tool_fallback("message", msg)
                        message_text = str(message_result or "").strip()
                        if message_text:
                            _update_followup_context_from_tool_execution(
                                session,
                                tool_name="message",
                                tool_args={"files": [artifact_path]},
                                fallback_source=source_hint,
                                tool_result=message_text,
                            )
                            if isinstance(message_metadata, dict):
                                executed_tools = message_metadata.get("executed_tools")
                                if not isinstance(executed_tools, list):
                                    executed_tools = []
                                if "message" not in executed_tools:
                                    executed_tools.append("message")
                                message_metadata["executed_tools"] = executed_tools
                                if message_text.lower().startswith("message sent to "):
                                    message_metadata["message_delivery_verified"] = True
                                if archive_replaced_directory:
                                    existing_evidence = message_metadata.get("completion_evidence")
                                    if isinstance(existing_evidence, dict):
                                        existing_evidence["artifact_paths"] = [artifact_path]
                                        message_metadata["completion_evidence"] = existing_evidence
                            _update_completion_evidence(
                                message_metadata,
                                session,
                                artifact_paths=[artifact_path],
                                artifact_verified=True,
                                delivery_paths=[artifact_path],
                                delivery_verified=message_text.lower().startswith("message sent to "),
                            )
                            return await progress_runtime.return_with_phase(message_text)
                    if artifact_path and not artifact_exists:
                        return await progress_runtime.return_with_phase(
                            "I couldn't verify the requested artifact because the target file still "
                            "does not exist. I won't claim the task is done without filesystem evidence.",
                            phase="error",
                        )
                if delivery_required and required_tool == "message" and not direct_delivery_verified:
                    return await progress_runtime.return_with_phase(
                        "I couldn't verify delivery because no file attachment was sent through "
                        "the message tool. I won't claim the file was sent without evidence.",
                        phase="error",
                    )
                metadata = getattr(msg, "metadata", None)
                summarize_file_analysis = bool(
                    required_tool == "read_file"
                    and isinstance(metadata, dict)
                    and metadata.get("file_analysis_mode")
                )
                if (
                    required_tool in raw_direct_tools
                    and not summarize_file_analysis
                    and not _should_summarize_raw_direct_result(required_tool, str(direct_result or ""))
                ):
                    return await progress_runtime.return_with_phase(direct_result)
                # Read-only direct tools still get an LLM-formatted summary.
                summary_messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            f"[TOOL RESULT: {required_tool}]\n{direct_result}\n\n"
                            "Use this tool result to answer the user's actual request in a clear, friendly "
                            "response in the user's language unless they explicitly ask for a different language. Do not ask the user to resend a "
                            "path or repeat the same file reference. Be concise and highlight the most "
                            "important information."
                        ),
                    }
                ]
                try:
                    request_overrides, _disable_tools = _active_llm_request_overrides(loop)
                    summary_response = await loop.provider.chat(
                        messages=summary_messages,
                        model=model,
                        **request_overrides,
                    )
                    if summary_response and summary_response.content:
                        return await progress_runtime.return_with_phase(summary_response.content)
                except Exception as e:
                    logger.warning(f"LLM summary failed for {required_tool}, returning raw result: {e}")
                # Fallback: return raw result if LLM still fails
                return await progress_runtime.return_with_phase(direct_result)
    # === END FAST PATH ===

    skip_plan_for_speed = (
        not is_background_task
        and (
            bool(required_tool)
            or continuity_source in (toolbacked_continuity_sources | coding_execution_continuity_sources)
            or (raw_user_word_count <= 12 and not coding_execution_context)
            or (_looks_like_short_confirmation(raw_user_text) and not coding_execution_context)
            or route_profile in {"CHAT", "RESEARCH"}
        )
    )
    plan = None
    if not required_tool and not skip_plan_for_speed:
        plan = await loop._plan_task(question_text)
        if plan:
            messages.append({"role": "user", "content": f"[SYSTEM PLAN]\n{plan}\n\nNow execute this plan step by step."})
    else:
        if required_tool:
            logger.info(f"Skipping plan for immediate-action task: required_tool={required_tool}")
        elif continuity_source in toolbacked_continuity_sources:
            logger.info(
                "Skipping plan for immediate-action continuity: "
                f"continuity_source={continuity_source}"
            )
        else:
            logger.info("Skipping plan for speed: short/follow-up/research route")

    messages = loop._apply_think_mode(messages, session)

    while iteration < loop.max_iterations:
        iteration += 1
        messages = await progress_runtime.inject_pending_interrupts(messages)

        if loop.context_guard.check_overflow(messages, model):
            logger.warning("Context overflow detected, compacting history")
            messages = await loop.compactor.compact(
                messages, loop.provider, model, keep_recent=10
            )
            if loop.context_guard.check_overflow(messages, model):
                logger.warning("Context still over limit after compaction")

        response, error = await loop._call_llm_with_fallback(messages, models_to_try)
        if not response:
            # User-friendly error: never expose raw exception / internal URLs
            error_hint = _sanitize_error(str(error)) if error else "unknown error"
            return await progress_runtime.return_with_phase(
                f"WARNING: All available AI models failed to respond.\n"
                f"Error: {error_hint}\n\n"
                f"Tip: Try /switch <model> to change model, or try again in a moment."
                ,
                phase="error",
            )

        if required_tool and response.has_tool_calls:
            if any(tc.name == required_tool for tc in response.tool_calls):
                required_tool = None
                tool_enforcement_retries = 0
            else:
                wrong_tools = ", ".join(tc.name for tc in response.tool_calls)
                if tool_enforcement_retries < max_tool_retry:
                    tool_enforcement_retries += 1
                    logger.warning(
                        f"Tool enforcement: expected '{required_tool}' but got other tools ({wrong_tools}) (iter {iteration})"
                    )
                    if response.content:
                        messages = loop.context.add_assistant_message(
                            messages, response.content, reasoning_content=response.reasoning_content
                        )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"SYSTEM: This request REQUIRES the '{required_tool}' tool. "
                                f"You called [{wrong_tools}] which is incorrect for this task. "
                                "Call the required tool now."
                            ),
                        }
                    )
                    continue

                fallback_result = await loop._execute_required_tool_fallback(required_tool, msg)
                if fallback_result is not None:
                    logger.warning(
                        f"Tool enforcement fallback executed for '{required_tool}' after wrong tool calls"
                    )
                    source_hint = str(message_metadata.get("required_tool_query") or "").strip()
                    if not source_hint:
                        source_hint = _resolve_query_text_from_message(msg)
                    _update_followup_context_from_tool_execution(
                        session,
                        tool_name=required_tool,
                        tool_args={},
                        fallback_source=source_hint,
                        tool_result=fallback_result,
                    )
                    return await progress_runtime.return_with_phase(fallback_result)
        if (
            requires_grounded_filesystem_inspection
            and response.has_tool_calls
            and not any(tc.name in grounded_filesystem_tools for tc in response.tool_calls)
            and not is_background_task
        ):
            if not grounded_filesystem_inspection_retried:
                grounded_filesystem_inspection_retried = True
                logger.warning(
                    "Grounded filesystem inspection enforcement: expected repository/file inspection tools "
                    f"but got {[tc.name for tc in response.tool_calls]} (iter {iteration})"
                )
                if response.content:
                    messages = loop.context.add_assistant_message(
                        messages,
                        response.content,
                        reasoning_content=response.reasoning_content,
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "SYSTEM: This request requires grounded filesystem inspection before you explain "
                            "the local folder, repo, project, app, config, or workspace docs. Call list_dir, read_file, find_files, "
                            "or exec to inspect local files first. Do not answer from guesswork or only "
                            "repeat filenames."
                        ),
                    }
                )
                continue
            return await progress_runtime.return_with_phase(
                "I couldn't verify a grounded project inspection because no filesystem inspection tool "
                "was used. I won't describe the local app, config, or repo from guesswork.",
                phase="error",
            )

        if response.has_tool_calls:
            tools_executed = True

        if (
            enforce_real_execution
            and not response.has_tool_calls
            and not tools_executed
            and not is_background_task
        ):
            if not immediate_action_retried:
                immediate_action_retried = True
                logger.warning(
                    "Immediate action enforcement: expected tool-backed execution "
                    f"but got text-only response (iter {iteration})"
                )
                if response.content:
                    messages = loop.context.add_assistant_message(
                        messages,
                        response.content,
                        reasoning_content=response.reasoning_content,
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "SYSTEM: This request requires real execution with tools or approved skills. "
                            "Do not answer with a guessed completion, filename, promise, or placeholder. "
                            "Call the necessary tool(s) now, or explicitly state the concrete execution blocker "
                            "if no suitable tool or permission exists."
                            + (
                                " For this turn, inspect the local filesystem first with list_dir, read_file, "
                                "find_files, or exec before you explain what the project, config, docs, or app is."
                                if requires_grounded_filesystem_inspection
                                else ""
                            )
                        ),
                    }
                )
                continue
            if requires_grounded_filesystem_inspection:
                return await progress_runtime.return_with_phase(
                    "I couldn't verify a grounded project inspection because no filesystem inspection "
                    "tool execution happened. I won't explain the local app, config, docs, or repo without evidence.",
                    phase="error",
                )
            return await progress_runtime.return_with_phase(
                "I couldn't verify completion because no tool or skill execution happened. "
                "I won't claim the task is done without evidence. Please retry with the "
                "required tool or provide the missing execution permission.",
                phase="error",
            )

        if required_tool and not response.has_tool_calls:
            if tool_enforcement_retries < max_tool_retry:
                tool_enforcement_retries += 1
                logger.warning(
                    f"Tool enforcement: expected '{required_tool}' but got text-only response (iter {iteration})"
                )
                if response.content:
                    messages = loop.context.add_assistant_message(
                        messages, response.content, reasoning_content=response.reasoning_content
                    )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"SYSTEM: For this request, you MUST call the '{required_tool}' tool now. "
                            "Do not answer from memory or estimation. Return a tool call."
                        ),
                    }
                )
                continue

            fallback_result = await loop._execute_required_tool_fallback(required_tool, msg)
            if fallback_result is not None:
                logger.warning(f"Tool enforcement fallback executed for '{required_tool}'")
                source_hint = str(message_metadata.get("required_tool_query") or "").strip()
                if not source_hint:
                    source_hint = _resolve_query_text_from_message(msg)
                _update_followup_context_from_tool_execution(
                    session,
                    tool_name=required_tool,
                    tool_args={},
                    fallback_source=source_hint,
                    tool_result=fallback_result,
                )
                return await progress_runtime.return_with_phase(fallback_result)

        if response.has_tool_calls:
            await progress_runtime.publish_phase("tool")

        if response.content:
            if response.reasoning_content:
                await progress_runtime.publish_reasoning(response.reasoning_content)
            if not response.has_tool_calls and not self_eval_retried and not is_background_task:
                passed, nudge = loop._self_evaluate(question_text, response.content)
                if not passed and nudge:
                    self_eval_retried = True
                    logger.warning(f"Self-eval: refusal detected, retrying (iter {iteration})")
                    await progress_runtime.publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": nudge})
                    continue

            if (
                not response.has_tool_calls
                and critic_retried < max_critic_retries
                and not is_weak_model
                and not tools_executed
                and not is_background_task
                and not skip_critic_for_speed
            ):
                score, feedback = await loop._critic_evaluate(question_text, response.content, model)
                if first_score is None:
                    first_score = score

                if score < critic_threshold and critic_retried < max_critic_retries:
                    critic_retried += 1
                    logger.warning(
                        f"Critic: score {score}/10 (threshold: {critic_threshold}), retrying ({critic_retried}/{max_critic_retries})"
                    )
                    await progress_runtime.publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
                    messages.append({"role": "user", "content": (
                        f"[CRITIC FEEDBACK - Score: {score}/10]\n{feedback}\n\n"
                        f"Please improve your response based on this feedback."
                    )})
                    continue
                else:
                    if critic_retried > 0:
                        await loop._log_lesson(
                            question=question_text,
                            feedback=feedback,
                            score_before=first_score or 0,
                            score_after=score,
                        )

            if (
                enforce_toolbacked_action
                and expected_artifact_path is not None
                and not response.has_tool_calls
                and not is_background_task
                and not expected_artifact_path.exists()
            ):
                _update_completion_evidence(
                    message_metadata,
                    session,
                    artifact_paths=[str(expected_artifact_path)],
                    artifact_verified=False,
                    delivery_verified=False,
                )
                if not artifact_verification_retried:
                    artifact_verification_retried = True
                    logger.warning(
                        "Artifact verification failed: expected path does not exist yet "
                        f"({expected_artifact_path})"
                    )
                    await progress_runtime.publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(
                        messages,
                        response.content,
                        reasoning_content=response.reasoning_content,
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"SYSTEM: The requested artifact still does not exist at "
                                f"'{explicit_artifact_path}'. Do not claim success yet. "
                                "Create or save the artifact at that path first, then answer."
                            ),
                        }
                    )
                    continue
                return await progress_runtime.return_with_phase(
                    "I couldn't verify the requested artifact because the target file still "
                    "does not exist. I won't claim the task is done without filesystem evidence.",
                    phase="error",
                )

            if (
                enforce_real_execution
                and delivery_required
                and not response.has_tool_calls
                and not is_background_task
                and not bool(message_metadata.get("message_delivery_verified"))
            ):
                session_metadata = getattr(session, "metadata", None)
                session_last_tool_context = (
                    session_metadata.get("last_tool_context")
                    if isinstance(session_metadata, dict)
                    else {}
                )
                if not isinstance(session_last_tool_context, dict):
                    session_last_tool_context = {}
                message_last_tool_context = (
                    message_metadata.get("last_tool_context")
                    if isinstance(message_metadata.get("last_tool_context"), dict)
                    else {}
                )
                delivery_candidate_path = str(
                    message_last_tool_context.get("path")
                    or session_last_tool_context.get("path")
                    or ""
                ).strip()
                if delivery_candidate_path:
                    verified_delivery_path, delivery_artifact_exists = _verify_completion_artifact_path(
                        loop,
                        delivery_candidate_path,
                    )
                else:
                    verified_delivery_path, delivery_artifact_exists = "", False
                _update_completion_evidence(
                    message_metadata,
                    session,
                    artifact_paths=[verified_delivery_path] if verified_delivery_path else None,
                    artifact_verified=delivery_artifact_exists if verified_delivery_path else None,
                    delivery_paths=[verified_delivery_path] if verified_delivery_path else None,
                    delivery_verified=False,
                )
                executed_tools = message_metadata.get("executed_tools")
                if (
                    isinstance(executed_tools, list)
                    and "message" not in executed_tools
                    and delivery_candidate_path
                ):
                    direct_delivery_result = await loop._execute_required_tool_fallback("message", msg)
                    direct_delivery_text = str(direct_delivery_result or "").strip()
                    if direct_delivery_text.lower().startswith("message sent to "):
                        source_hint = str(message_metadata.get("required_tool_query") or "").strip()
                        if not source_hint:
                            source_hint = _resolve_query_text_from_message(msg)
                        _update_followup_context_from_tool_execution(
                            session,
                            tool_name="message",
                            tool_args={},
                            fallback_source=source_hint,
                            tool_result=direct_delivery_text,
                        )
                        executed_tools.append("message")
                        message_metadata["executed_tools"] = executed_tools
                        message_metadata["message_delivery_verified"] = True
                        logger.info(
                            "Delivery verification recovered via direct message fallback "
                            f"after executed_tools={executed_tools}"
                        )
                        return await progress_runtime.return_with_phase(direct_delivery_text)
                if not delivery_verification_retried:
                    delivery_verification_retried = True
                    logger.warning(
                        "Delivery verification failed: requested file/message delivery has not "
                        "been verified through the message tool yet"
                    )
                    await progress_runtime.publish_draft(response.content, phase="thinking")
                    messages = loop.context.add_assistant_message(
                        messages,
                        response.content,
                        reasoning_content=response.reasoning_content,
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "SYSTEM: The requested file delivery has not happened yet. "
                                "Do not claim the file was sent. Use the 'message' tool with "
                                "its 'files' argument to send the real local file to the current "
                                "chat now, or explain the concrete blocker if delivery is not possible."
                            ),
                        }
                    )
                    continue
                return await progress_runtime.return_with_phase(
                    "I couldn't verify delivery because no file attachment was sent through "
                    "the message tool. I won't claim the file was sent without evidence.",
                    phase="error",
                )

            messages = loop.context.add_assistant_message(messages, response.content, reasoning_content=response.reasoning_content)
            if not response.has_tool_calls:
                return await progress_runtime.return_with_phase(response.content)

        if response.has_tool_calls:
            messages = await loop._process_tool_calls(msg, messages, response, session)
            passthrough_payload = None
            if isinstance(message_metadata, dict):
                passthrough_payload = message_metadata.pop("tool_result_passthrough", None)
            if passthrough_payload is None:
                session_metadata = getattr(session, "metadata", None)
                if isinstance(session_metadata, dict):
                    passthrough_payload = session_metadata.pop("tool_result_passthrough", None)
            if isinstance(passthrough_payload, dict):
                if bool(passthrough_payload.get("continue_loop")):
                    continuation_message = str(passthrough_payload.get("append_message") or "").strip()
                    if continuation_message:
                        messages.append({"role": "user", "content": continuation_message})
                    logger.info(
                        "Continuing agent loop after tool passthrough note: "
                        f"tool={passthrough_payload.get('tool') or 'unknown'} "
                        f"reason={passthrough_payload.get('reason') or 'unknown'}"
                    )
                    continue
                passthrough_execute_tool = str(
                    passthrough_payload.get("execute_tool") or ""
                ).strip()
                if passthrough_execute_tool:
                    passthrough_args = passthrough_payload.get("arguments") or {}
                    logger.info(
                        "Executing passthrough fallback tool after tool execution: "
                        f"tool={passthrough_execute_tool} reason={passthrough_payload.get('reason') or 'unknown'}"
                    )
                    fallback_result = await loop.tools.execute(
                        passthrough_execute_tool,
                        passthrough_args,
                    )
                    return await progress_runtime.return_with_phase(
                        str(fallback_result or "").strip(),
                        phase=str(passthrough_payload.get("phase") or "tool").strip() or "tool",
                    )
                passthrough_content = str(passthrough_payload.get("content") or "").strip()
                passthrough_phase = str(passthrough_payload.get("phase") or "done").strip() or "done"
                if passthrough_content:
                    logger.info(
                        "Returning tool result passthrough after tool execution: "
                        f"tool={passthrough_payload.get('tool') or 'unknown'} phase={passthrough_phase}"
                    )
                    return await progress_runtime.return_with_phase(
                        passthrough_content,
                        phase=passthrough_phase,
                    )
            messages = await progress_runtime.inject_pending_interrupts(messages)
        else:
            return await progress_runtime.return_with_phase(response.content)
    return await progress_runtime.return_with_phase("I've completed processing but have no response to give.")
