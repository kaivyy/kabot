"""Delegated AgentLoop wrapper methods extracted from kabot.agent.loop."""

from __future__ import annotations

import re
from typing import Any

from kabot.agent.cron_fallback_nlp import REMINDER_KEYWORDS, WEATHER_KEYWORDS
from kabot.agent.loop_core import directives_runtime as loop_directives_runtime
from kabot.agent.loop_core import execution_runtime as loop_execution_runtime
from kabot.agent.loop_core import message_runtime as loop_message_runtime
from kabot.agent.loop_core import quality_runtime as loop_quality_runtime
from kabot.agent.loop_core import routing_runtime as loop_routing_runtime
from kabot.agent.loop_core import session_flow as loop_session_flow
from kabot.agent.loop_core import tool_enforcement as loop_tool_enforcement
from kabot.bus.events import InboundMessage, OutboundMessage

_APPROVAL_CMD_RE = re.compile(r"^\s*/(approve|deny)(?:\s+([A-Za-z0-9_-]+))?\s*$", re.IGNORECASE)


class AgentLoopDelegatesMixin:
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        return await loop_message_runtime.process_message(self, msg)

    @staticmethod
    def _parse_approval_command(content: str) -> tuple[str, str | None] | None:
        """Parse /approve or /deny command from user message."""
        if not content:
            return None
        match = _APPROVAL_CMD_RE.match(content.strip())
        if not match:
            return None
        action = match.group(1).lower()
        approval_id = match.group(2)
        return action, approval_id

    async def _process_pending_exec_approval(
        self,
        msg: InboundMessage,
        action: str,
        approval_id: str | None = None,
    ) -> OutboundMessage:
        return await loop_message_runtime.process_pending_exec_approval(
            self,
            msg,
            action=action,
            approval_id=approval_id,
        )

    def _route_context_for_message(self, msg: InboundMessage) -> dict[str, Any]:
        return loop_routing_runtime.route_context_for_message(self, msg)

    def _resolve_route_for_message(self, msg: InboundMessage) -> dict[str, str]:
        return loop_routing_runtime.resolve_route_for_message(self, msg)

    def _get_session_key(self, msg: InboundMessage) -> str:
        return loop_session_flow.get_session_key(self, msg)

    def _resolve_models_for_message(self, msg: InboundMessage) -> list[str]:
        return loop_routing_runtime.resolve_models_for_message(self, msg)

    def _resolve_model_for_message(self, msg: InboundMessage) -> str:
        return loop_routing_runtime.resolve_model_for_message(self, msg)

    def _resolve_agent_id_for_message(self, msg: InboundMessage) -> str:
        return loop_routing_runtime.resolve_agent_id_for_message(self, msg)

    async def _init_session(self, msg: InboundMessage) -> Any:
        return await loop_session_flow.init_session(self, msg)

    async def _run_simple_response(self, msg: InboundMessage, messages: list) -> str | None:
        return await loop_execution_runtime.run_simple_response(self, msg, messages)

    async def _run_agent_loop(self, msg: InboundMessage, messages: list, session: Any) -> str | None:
        return await loop_execution_runtime.run_agent_loop(self, msg, messages, session)

    def _self_evaluate(self, question: str, answer: str) -> tuple[bool, str | None]:
        return loop_quality_runtime.self_evaluate(self, question, answer)

    _IMMEDIATE_ACTION_PATTERNS = loop_quality_runtime.IMMEDIATE_ACTION_PATTERNS

    _REMINDER_KEYWORDS = REMINDER_KEYWORDS
    _WEATHER_KEYWORDS = WEATHER_KEYWORDS

    def _existing_schedule_titles(self) -> list[str]:
        return loop_tool_enforcement.existing_schedule_titles(self)

    def _required_tool_for_query(self, question: str) -> str | None:
        return loop_tool_enforcement.required_tool_for_query_for_loop(self, question)

    def _infer_required_tool_from_history(
        self,
        followup_text: str,
        history: list[dict[str, Any]] | None,
    ) -> tuple[str | None, str | None]:
        return loop_tool_enforcement.infer_required_tool_from_history_for_loop(
            self,
            followup_text,
            history,
        )

    def _make_unique_schedule_title(self, base_title: str) -> str:
        return loop_tool_enforcement.make_unique_schedule_title_for_loop(self, base_title)

    def _build_group_id(self, title: str) -> str:
        return loop_tool_enforcement.build_group_id_for_loop(self, title)

    async def _execute_required_tool_fallback(self, required_tool: str, msg: InboundMessage) -> str | None:
        return await loop_tool_enforcement.execute_required_tool_fallback(self, required_tool, msg)

    async def _plan_task(self, question: str) -> str | None:
        return await loop_quality_runtime.plan_task(self, question)

    def _is_weak_model(self, model: str) -> bool:
        return loop_quality_runtime.is_weak_model(self, model)

    async def _critic_evaluate(self, question: str, answer: str, model: str | None = None) -> tuple[int, str]:
        return await loop_quality_runtime.critic_evaluate(self, question, answer, model)

    async def _log_lesson(
        self,
        question: str,
        feedback: str,
        score_before: int,
        score_after: int,
    ) -> None:
        await loop_quality_runtime.log_lesson(self, question, feedback, score_before, score_after)

    async def _call_llm_with_fallback(
        self,
        messages: list,
        models: list,
        include_tools_initial: bool = True,
    ) -> tuple[Any | None, Exception | None]:
        return await loop_execution_runtime.call_llm_with_fallback(
            self,
            messages,
            models,
            include_tools_initial=include_tools_initial,
        )

    async def _process_tool_calls(self, msg: InboundMessage, messages: list, response: Any, session: Any) -> list:
        return await loop_execution_runtime.process_tool_calls(self, msg, messages, response, session)

    def _format_tool_result(self, result: Any) -> str:
        return loop_execution_runtime.format_tool_result(self, result)

    async def _finalize_session(self, msg: InboundMessage, session: Any, final_content: str | None) -> OutboundMessage:
        return await loop_session_flow.finalize_session(self, msg, session, final_content)

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        return await loop_message_runtime.process_system_message(self, msg)

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        model_override: str | None = None,
        fallback_overrides: list[str] | None = None,
        suppress_post_response_warmup: bool = False,
        probe_mode: bool = False,
        persist_history: bool = False,
    ) -> str:
        metadata: dict[str, Any] = {}
        model_text = str(model_override or "").strip()
        if model_text:
            metadata["model_override"] = model_text
            metadata["model_override_source"] = "direct"
        if isinstance(fallback_overrides, list):
            normalized_fallbacks = [str(item).strip() for item in fallback_overrides if str(item).strip()]
            if normalized_fallbacks:
                metadata["model_fallbacks"] = normalized_fallbacks[:8]
        if suppress_post_response_warmup:
            metadata["suppress_post_response_warmup"] = True
        if probe_mode:
            metadata["probe_mode"] = True
        if persist_history:
            metadata["persist_history"] = True

        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            _session_key=session_key,
            metadata=metadata,
        )
        response = await self._process_message(msg)
        return response.content if response else ""

    async def process_isolated(
        self,
        content: str,
        channel: str = "cli",
        chat_id: str = "direct",
        job_id: str = "",
    ) -> str:
        return await loop_message_runtime.process_isolated(
            self,
            content,
            channel=channel,
            chat_id=chat_id,
            job_id=job_id,
        )

    def _apply_think_mode(self, messages: list, session: Any) -> list:
        return loop_directives_runtime.apply_think_mode(self, messages, session)

    def _should_log_verbose(self, session: Any) -> bool:
        return loop_directives_runtime.should_log_verbose(self, session)

    def _format_verbose_output(self, tool_name: str, tool_result: str, tokens_used: int) -> str:
        return loop_directives_runtime.format_verbose_output(self, tool_name, tool_result, tokens_used)

    def _get_tool_permissions(self, session: Any) -> dict:
        return loop_directives_runtime.get_tool_permissions(self, session)
