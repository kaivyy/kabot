"""Directive and verbose helper logic extracted from AgentLoop."""

from __future__ import annotations

from typing import Any

from loguru import logger


def apply_think_mode(loop: Any, messages: list, session: Any) -> list:
    """Apply think mode directive by injecting reasoning prompt into context."""
    try:
        directives = session.metadata.get("directives", {})
        if not isinstance(directives, dict):
            logger.warning("Directives metadata corrupted, using defaults")
            directives = {}

        if not directives.get("think"):
            return messages

        reasoning_prompt = {
            "role": "system",
            "content": (
                "Think step-by-step. Show your reasoning process explicitly before taking action. "
                "Consider edge cases, alternative approaches, and potential issues. "
                "When analyzing code, read related files to understand full context."
            ),
        }

        messages.insert(0, reasoning_prompt)
        logger.debug("Think mode applied: reasoning prompt injected")
        return messages

    except Exception as e:
        logger.error(f"Failed to apply think mode: {e}")
        return messages


def should_log_verbose(loop: Any, session: Any) -> bool:
    """Check if verbose logging directive is enabled for the current session."""
    try:
        directives = session.metadata.get("directives", {})
        if not isinstance(directives, dict):
            return False
        return directives.get("verbose", False)
    except Exception as e:
        logger.error(f"Failed to check verbose mode: {e}")
        return False


def format_verbose_output(loop: Any, tool_name: str, tool_result: str, tokens_used: int) -> str:
    """Format verbose debug output for tool execution details."""
    return (
        f"\n\n[DEBUG] Tool: {tool_name}\n"
        f"[DEBUG] Tokens: {tokens_used}\n"
        f"[DEBUG] Result:\n{tool_result}\n"
    )


def get_tool_permissions(loop: Any, session: Any) -> dict:
    """Get tool execution permissions based on elevated directive status."""
    try:
        elevated = session.metadata.get("directives", {}).get("elevated", False)

        return {
            "auto_approve": elevated,
            "restrict_to_workspace": not elevated,
            "allow_high_risk": elevated,
        }
    except Exception as e:
        logger.error(f"Failed to get tool permissions: {e}")
        return {
            "auto_approve": False,
            "restrict_to_workspace": True,
            "allow_high_risk": False,
        }
