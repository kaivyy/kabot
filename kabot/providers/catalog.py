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
        id="openai/gpt-4o-mini",
        name="GPT-4o Mini",
        provider="openai",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.15, output_1m=0.6),
        capabilities=["vision", "tools", "json"],
        is_premium=True
    ),
    ModelMetadata(
        id="openai/gpt-4-turbo",
        name="GPT-4 Turbo",
        provider="openai",
        context_window=128000,
        pricing=ModelPricing(input_1m=10.0, output_1m=30.0),
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
    ModelMetadata(
        id="openai/o1-mini",
        name="OpenAI o1 Mini",
        provider="openai",
        context_window=128000,
        pricing=ModelPricing(input_1m=3.0, output_1m=12.0),
        capabilities=["reasoning", "tools"],
        is_premium=True
    ),
    # OpenClaw Reference Models
    ModelMetadata(
        id="openai/gpt-5.1-codex",
        name="GPT-5.1 Codex",
        provider="openai",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0), # Unknown
        capabilities=["tools", "coding"],
        is_premium=True
    ),
    ModelMetadata(
        id="openai-codex/gpt-5.3-codex",
        name="GPT-5.3 Codex Pro",
        provider="openai-codex",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0), # Unknown
        capabilities=["tools", "coding", "reasoning"],
        is_premium=True
    ),

    # --- Anthropic ---
    ModelMetadata(
        id="anthropic/claude-3-5-sonnet-20241022",
        name="Claude 3.5 Sonnet (New)",
        provider="anthropic",
        context_window=200000,
        pricing=ModelPricing(input_1m=3.0, output_1m=15.0),
        capabilities=["vision", "tools", "json"],
        is_premium=True
    ),
    ModelMetadata(
        id="anthropic/claude-3-5-sonnet-20240620",
        name="Claude 3.5 Sonnet (Old)",
        provider="anthropic",
        context_window=200000,
        pricing=ModelPricing(input_1m=3.0, output_1m=15.0),
        capabilities=["vision", "tools", "json"],
        is_premium=True
    ),
    ModelMetadata(
        id="anthropic/claude-3-5-haiku-20241022",
        name="Claude 3.5 Haiku",
        provider="anthropic",
        context_window=200000,
        pricing=ModelPricing(input_1m=1.0, output_1m=5.0),
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
    # OpenClaw Reference Models
    ModelMetadata(
        id="anthropic/claude-opus-4-6",
        name="Claude Opus 4.6",
        provider="anthropic",
        context_window=200000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "tools"],
        is_premium=True
    ),
    ModelMetadata(
        id="anthropic/claude-sonnet-4-5",
        name="Claude Sonnet 4.5",
        provider="anthropic",
        context_window=200000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
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
    ModelMetadata(
        id="google/gemini-1.5-flash",
        name="Gemini 1.5 Flash",
        provider="google",
        context_window=1000000,
        pricing=ModelPricing(input_1m=0.075, output_1m=0.3),
        capabilities=["vision", "tools", "json"],
        is_premium=True
    ),
    ModelMetadata(
        id="google-gemini-cli/gemini-3-pro-preview",
        name="Gemini 3 Pro Preview",
        provider="google-gemini-cli",
        context_window=2000000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
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
        capabilities=["tools", "long-context"],
        is_premium=True
    ),
    ModelMetadata(
        id="moonshot/kimi-k2-thinking",
        name="Kimi K2 Thinking",
        provider="moonshot",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning"],
        is_premium=True
    ),
    ModelMetadata(
        id="moonshot/kimi-k2-turbo-preview",
        name="Kimi K2 Turbo",
        provider="moonshot",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["tools"],
        is_premium=True
    ),
    ModelMetadata(
        id="kimi-coding/k2p5",
        name="Kimi Code K2.5",
        provider="kimi-coding",
        context_window=200000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["coding", "tools"],
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
    ),
    ModelMetadata(
        id="minimax/MiniMax-M2.1-lightning",
        name="MiniMax M2.1 Lightning",
        provider="minimax",
        context_window=200000,
        pricing=ModelPricing(input_1m=1.0, output_1m=2.0), # Estimated low
        capabilities=["tools"],
        is_premium=True
    ),

    # --- Qwen ---
    ModelMetadata(
        id="qwen-portal/coder-model",
        name="Qwen Coder",
        provider="qwen-portal",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["coding", "tools"],
        is_premium=True
    ),
    ModelMetadata(
        id="qwen-portal/vision-model",
        name="Qwen Vision",
        provider="qwen-portal",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "tools"],
        is_premium=True
    ),

    # --- Others ---
    ModelMetadata(
        id="zai/glm-4.7",
        name="Z.AI GLM 4.7",
        provider="zai",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["tools"],
        is_premium=True
    ),
    ModelMetadata(
        id="venice/llama-3.3-70b",
        name="Venice Llama 3.3",
        provider="venice",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="together/moonshotai/Kimi-K2.5",
        name="Together Kimi",
        provider="together",
        context_window=256000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    )
]

def populate_registry(registry):
    """Populate the registry with the static catalog."""
    for metadata in STATIC_MODEL_CATALOG:
        registry.register(metadata)
        
    # Register common aliases matching OpenClaw's model-reference
    # OpenAI
    registry.register_alias("gpt4", "openai/gpt-4o")
    registry.register_alias("gpt4o", "openai/gpt-4o")
    registry.register_alias("gpt4m", "openai/gpt-4o-mini")
    registry.register_alias("o1", "openai/o1-preview")
    registry.register_alias("o1m", "openai/o1-mini")
    registry.register_alias("codex", "openai/gpt-5.1-codex")
    registry.register_alias("codex-pro", "openai-codex/gpt-5.3-codex")

    # Anthropic
    registry.register_alias("sonnet", "anthropic/claude-3-5-sonnet-20241022")
    registry.register_alias("sonnet-old", "anthropic/claude-3-5-sonnet-20240620")
    registry.register_alias("haiku", "anthropic/claude-3-5-haiku-20241022")
    registry.register_alias("opus", "anthropic/claude-3-opus-20240229")
    
    # Google
    registry.register_alias("gemini", "google/gemini-1.5-pro")
    registry.register_alias("flash", "google/gemini-1.5-flash")
    registry.register_alias("gemini-pro", "google-gemini-cli/gemini-3-pro-preview")
    
    # Moonshot
    registry.register_alias("kimi", "moonshot/kimi-k2.5")
    registry.register_alias("kimi-think", "moonshot/kimi-k2-thinking")
    registry.register_alias("kimi-fast", "moonshot/kimi-k2-turbo-preview")
    registry.register_alias("kimi-code", "kimi-coding/k2p5")
    
    # MiniMax
    registry.register_alias("minimax", "minimax/MiniMax-M2.1")
    registry.register_alias("minimax-fast", "minimax/MiniMax-M2.1-lightning")
    
    # Qwen & Others
    registry.register_alias("qwen-code", "qwen-portal/coder-model")
    registry.register_alias("glm", "zai/glm-4.7")
    registry.register_alias("venice", "venice/llama-3.3-70b")
    registry.register_alias("together-kimi", "together/moonshotai/Kimi-K2.5")
