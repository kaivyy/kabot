"""Static catalog of premium AI models with pricing and context data."""

from kabot.providers.models import ModelMetadata, ModelPricing

# Curated catalog based on OpenClaw and official provider data
STATIC_MODEL_CATALOG = [
    # --- OpenAI ---
    ModelMetadata(
        id="openai/gpt-4o",
        name="GPT-4o",
        provider="openai",
        context_window=128000,
        pricing=ModelPricing(input_1m=5.0, output_1m=15.0),
        capabilities=["vision", "tools", "json"],
        is_premium=True
    ),
    ModelMetadata(
        id="openai/o1-preview",
        name="OpenAI o1 Preview",
        provider="openai",
        context_window=128000,
        pricing=ModelPricing(input_1m=15.0, output_1m=60.0),
        capabilities=["reasoning", "tools"],
        is_premium=True
    ),
    
    # --- Anthropic ---
    ModelMetadata(
        id="anthropic/claude-3-5-sonnet-20240620",
        name="Claude 3.5 Sonnet",
        provider="anthropic",
        context_window=200000,
        pricing=ModelPricing(input_1m=3.0, output_1m=15.0),
        capabilities=["vision", "tools", "json"],
        is_premium=True
    ),
    ModelMetadata(
        id="anthropic/claude-3-opus-20240229",
        name="Claude 3 Opus",
        provider="anthropic",
        context_window=200000,
        pricing=ModelPricing(input_1m=15.0, output_1m=75.0),
        capabilities=["vision", "tools"],
        is_premium=True
    ),
    
    # --- Google ---
    ModelMetadata(
        id="google/gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider="google",
        context_window=2000000,
        pricing=ModelPricing(input_1m=3.5, output_1m=10.5),
        capabilities=["vision", "tools", "json"],
        is_premium=True
    ),
    
    # --- Moonshot (Kimi) ---
    ModelMetadata(
        id="moonshot/kimi-k2.5",
        name="Kimi K2.5",
        provider="moonshot",
        context_window=256000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0), # Varies
        capabilities=["tools"],
        is_premium=True
    ),
    
    # --- MiniMax ---
    ModelMetadata(
        id="minimax/MiniMax-M2.1",
        name="MiniMax M2.1",
        provider="minimax",
        context_window=200000,
        pricing=ModelPricing(input_1m=15.0, output_1m=60.0),
        capabilities=["tools"],
        is_premium=True
    )
]

def populate_registry(registry):
    """Populate the registry with the static catalog."""
    for metadata in STATIC_MODEL_CATALOG:
        registry.register(metadata)
