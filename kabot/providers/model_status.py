"""Model status tracking for setup wizard."""

from kabot.providers.catalog import STATIC_MODEL_CATALOG

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
    "groq/meta-llama/llama-4-scout-17b-16e-instruct",
    "groq/llama3-70b-8192",
    "groq/mixtral-8x7b-32768",
}

CATALOG_ONLY = {
    "openai/gpt-5.1-codex",
    "openai-codex/gpt-5.3-codex",
    "openai-codex/gpt-5.3-codex-spark",
    "qwen-portal/coder-model",
    "qwen-portal/vision-model",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-sonnet-4-5",
    "google-gemini-cli/gemini-3-pro-preview",
    "moonshot/kimi-k2.5",
    "minimax/MiniMax-M2.1",
    "mistral/mistral-large-latest",
    "mistral/pixtral-large-latest",
    "kilocode/anthropic/claude-opus-4.6",
    "kilocode/openai/gpt-5.2",
    "together/moonshotai/Kimi-K2.5",
    "together/meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "together/deepseek-ai/DeepSeek-R1",
    "venice/llama-3.3-70b",
    "venice/claude-opus-45",
    "huggingface/deepseek-ai/DeepSeek-R1",
    "huggingface/deepseek-ai/DeepSeek-V3.1",
    "qianfan/deepseek-v3.2",
    "qianfan/ernie-5.0-thinking-preview",
    "nvidia/nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/meta/llama-3.3-70b-instruct",
    "opencode/claude-opus-4-6",
    "xai/grok-4.1-mini",
    "cerebras/zai-glm-4.7",
    "xiaomi/mimo-v2-flash",
    "volcengine/doubao-seed-1-8-251228",
    "byteplus/seed-1-8-251228",
}

# Keep setup status in sync with the static model registry.
for _metadata in STATIC_MODEL_CATALOG:
    if _metadata.id not in WORKING_MODELS:
        CATALOG_ONLY.add(_metadata.id)

UNSUPPORTED_PROVIDERS = {
    "kimi-coding",
    "google-gemini-cli",
}

def get_model_status(model_id: str) -> str:
    """Return 'working', 'catalog', 'unsupported', or 'unknown'."""
    # Validate input
    if not model_id:
        return "unknown"

    if model_id in WORKING_MODELS:
        return "working"

    # Check catalog before unsupported providers to avoid false negatives
    if model_id in CATALOG_ONLY:
        return "catalog"

    provider = model_id.split("/")[0] if "/" in model_id else model_id
    if provider in UNSUPPORTED_PROVIDERS:
        return "unsupported"

    return "unknown"

def get_status_indicator(status: str) -> str:
    """Return visual indicator for status."""
    indicators = {
        # ASCII-only markers to avoid mojibake in non-UTF8 terminals.
        "working": "OK",
        "catalog": "!",
        "unsupported": "X",
        "unknown": "?",
    }
    return indicators.get(status, "?")

