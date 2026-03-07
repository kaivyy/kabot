"""Pricing definitions for different AI models."""

# Default costs per 1 million tokens (USD)
# Source: Common market pricing or OpenClaw defaults
# Format: { "model_prefix": { "input": USD_PER_1M, "output": USD_PER_1M } }
MODEL_PRICING = {
    # OpenRouter / Common models
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "gemini-pro": {"input": 0.50, "output": 1.50},
    "gemini-flash": {"input": 0.10, "output": 0.30},

    # Chinese Providers (Minimax, Qwen, Deepseek)
    "minimax/": {"input": 0.15, "output": 0.15},
    "deepseek/": {"input": 0.14, "output": 0.28},
    "qwen/": {"input": 0.20, "output": 0.20},

    # Groq / Llama
    "groq/llama-4": {"input": 0.0, "output": 0.0}, # High performance, often free/low tier
    "groq/llama-3": {"input": 0.05, "output": 0.10},

    # Default fallback for unknown models
    "default": {"input": 1.0, "output": 3.0}
}

def resolve_model_pricing(model_id: str) -> dict[str, float]:
    """Resolve input/output costs for a given model ID."""
    mid = str(model_id or "").lower()

    # Try exact match
    if mid in MODEL_PRICING:
        return MODEL_PRICING[mid]

    # Try prefix match
    for prefix, prices in MODEL_PRICING.items():
        if prefix != "default" and mid.startswith(prefix):
            return prices

    return MODEL_PRICING["default"]

def estimate_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost based on token counts."""
    pricing = resolve_model_pricing(model_id)
    input_usd = (input_tokens / 1_000_000) * pricing["input"]
    output_usd = (output_tokens / 1_000_000) * pricing["output"]
    return input_usd + output_usd
