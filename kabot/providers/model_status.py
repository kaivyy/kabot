"""Model status tracking for setup wizard."""

WORKING_MODELS = {
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/o1-preview",
    "openai/o1-mini",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-3-5-haiku-20241022",
    "anthropic/claude-3-opus-20240229",
    "google/gemini-1.5-pro",
    "google/gemini-1.5-flash",
    "groq/llama3-70b-8192",
    "groq/mixtral-8x7b-32768",
}

CATALOG_ONLY = {
    "openai/gpt-5.1-codex",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-sonnet-4-5",
    "google-gemini-cli/gemini-3-pro-preview",
    "moonshot/kimi-k2.5",
    "minimax/MiniMax-M2.1",
}

UNSUPPORTED_PROVIDERS = {
    "openai-codex",
    "kimi-coding",
    "google-gemini-cli",
    "qwen-portal",
}

def get_model_status(model_id: str) -> str:
    """Return 'working', 'catalog', 'unsupported', or 'unknown'."""
    if model_id in WORKING_MODELS:
        return "working"

    provider = model_id.split("/")[0] if "/" in model_id else model_id
    if provider in UNSUPPORTED_PROVIDERS:
        return "unsupported"

    if model_id in CATALOG_ONLY:
        return "catalog"

    return "unknown"

def get_status_indicator(status: str) -> str:
    """Return visual indicator for status."""
    indicators = {
        "working": "✓",
        "catalog": "⚠",
        "unsupported": "✗",
        "unknown": "?",
    }
    return indicators.get(status, "?")
