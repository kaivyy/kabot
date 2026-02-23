"""Tool policy profiles for access control."""

from __future__ import annotations

from typing import Any

# Tool groups for easier policy management
TOOL_GROUPS = {
    "fs": ["read_file", "write_file", "edit_file", "list_dir"],
    "runtime": ["exec", "spawn"],
    "sessions": ["session_status", "message"],
    "web": ["web_search", "web_fetch", "browser"],
    "memory": ["save_memory", "get_memory", "memory_search", "knowledge_learn"],
    "automation": ["cron"],
    "google": ["gmail", "google_calendar", "google_docs", "google_drive"],
    "analysis": ["stock", "crypto", "stock_analysis", "weather", "speedtest"],
    "system": ["get_system_info", "cleanup_system", "get_process_memory", "server_monitor"],
}

# Tool access profiles
TOOL_PROFILES = {
    "minimal": {
        "allow": ["session_status"],
        "deny": None,
        "description": "Minimal access - only session status",
    },
    "coding": {
        "allow": ["@fs", "@web", "@memory", "session_status"],
        "deny": ["@automation", "@google", "@runtime"],
        "description": "Coding assistant - filesystem, web, memory",
    },
    "messaging": {
        "allow": ["@sessions", "@memory", "@google", "weather"],
        "deny": ["@runtime", "@automation"],
        "description": "Messaging assistant - sessions, memory, Google suite",
    },
    "analysis": {
        "allow": ["@analysis", "@web", "@memory", "session_status"],
        "deny": ["@runtime", "@automation", "@fs"],
        "description": "Analysis assistant - stocks, crypto, weather",
    },
    "full": {
        "allow": None,  # Allow all
        "deny": None,
        "description": "Full access - all tools available",
    },
}

# Owner-only tools (require owner permission)
OWNER_ONLY_TOOLS = ["cron", "exec", "spawn", "cleanup_system"]


class ToolPolicy:
    """Tool access policy."""

    def __init__(
        self,
        allow: list[str] | None = None,
        deny: list[str] | None = None,
    ):
        self.allow = allow
        self.deny = deny

    def expand_groups(self) -> set[str]:
        """Expand group references (@fs, @web, etc.) to actual tool names."""
        expanded = set()

        if self.allow is None:
            # Allow all
            return set()

        for item in self.allow:
            if item.startswith("@"):
                group_name = item[1:]
                if group_name in TOOL_GROUPS:
                    expanded.update(TOOL_GROUPS[group_name])
            else:
                expanded.add(item)

        return expanded

    def is_allowed(self, tool_name: str) -> bool:
        """Check if tool is allowed by this policy."""
        # If allow is None, allow all (unless explicitly denied)
        if self.allow is None:
            if self.deny is None:
                return True
            # Check deny list
            deny_expanded = set()
            for item in self.deny:
                if item.startswith("@"):
                    group_name = item[1:]
                    if group_name in TOOL_GROUPS:
                        deny_expanded.update(TOOL_GROUPS[group_name])
                else:
                    deny_expanded.add(item)
            return tool_name not in deny_expanded

        # Check allow list
        allowed = self.expand_groups()
        return tool_name in allowed


def resolve_profile_policy(profile_name: str) -> ToolPolicy:
    """Resolve a profile name to a ToolPolicy."""
    profile = TOOL_PROFILES.get(profile_name, TOOL_PROFILES["full"])
    return ToolPolicy(
        allow=profile.get("allow"),
        deny=profile.get("deny"),
    )


def is_owner_only_tool(tool_name: str) -> bool:
    """Check if tool requires owner permission."""
    return tool_name in OWNER_ONLY_TOOLS


def apply_tool_policy(tools: list[str], policy: ToolPolicy) -> list[str]:
    """Filter tools list based on policy."""
    return [tool for tool in tools if policy.is_allowed(tool)]
