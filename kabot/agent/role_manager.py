AGENT_ROLES = {
    "master": {
        "description": "Coordinates tasks and makes high-level decisions",
        "default_model": "openai/gpt-4o",
        "capabilities": ["planning", "coordination", "decision_making"]
    },
    "brainstorming": {
        "description": "Generates creative ideas and explores approaches",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
        "capabilities": ["ideation", "analysis", "exploration"]
    },
    "executor": {
        "description": "Executes code and performs file operations",
        "default_model": "moonshot/kimi-k2.5",
        "capabilities": ["code_execution", "file_operations", "tool_usage"]
    },
    "verifier": {
        "description": "Reviews code and validates results",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
        "capabilities": ["code_review", "testing", "validation"]
    }
}

def get_role_config(role: str) -> dict:
    return AGENT_ROLES.get(role, {})

def list_roles() -> list[str]:
    return list(AGENT_ROLES.keys())
