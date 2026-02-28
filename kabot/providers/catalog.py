"""Static catalog of premium AI models with pricing and context data."""

from kabot.providers.models import ModelMetadata, ModelPricing

# Curated catalog based on Kabot and official provider data
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
    # Kabot Reference Models
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
        id="openai/gpt-5.2-codex",
        name="GPT-5.2 Codex",
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
    ModelMetadata(
        id="openai-codex/gpt-5.3-codex-spark",
        name="GPT-5.3 Codex Spark",
        provider="openai-codex",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
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
    # Kabot Reference Models
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
        id="google/gemini-3.1-pro",
        name="Gemini 3.1 Pro",
        provider="google",
        context_window=2000000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "tools", "json", "reasoning"],
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
    ModelMetadata(
        id="google-gemini-cli/gemini-3.1-pro",
        name="Gemini 3.1 Pro (CLI)",
        provider="google-gemini-cli",
        context_window=2000000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "tools", "json", "reasoning"],
        is_premium=True
    ),

    # --- Mistral ---
    ModelMetadata(
        id="mistral/mistral-large-latest",
        name="Mistral Large Latest",
        provider="mistral",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["tools", "json"],
        is_premium=True
    ),
    ModelMetadata(
        id="mistral/pixtral-large-latest",
        name="Pixtral Large Latest",
        provider="mistral",
        context_window=128000,
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

    # --- Kilo Gateway ---
    ModelMetadata(
        id="kilocode/anthropic/claude-opus-4.6",
        name="Kilo Claude Opus 4.6",
        provider="kilocode",
        context_window=1000000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "tools", "reasoning"],
        is_premium=True
    ),
    ModelMetadata(
        id="kilocode/openai/gpt-5.2",
        name="Kilo GPT-5.2",
        provider="kilocode",
        context_window=400000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "tools", "reasoning"],
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
    ),
    ModelMetadata(
        id="together/meta-llama/Llama-4-Scout-17B-16E-Instruct",
        name="Together Llama 4 Scout",
        provider="together",
        context_window=10000000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="together/deepseek-ai/DeepSeek-R1",
        name="Together DeepSeek R1",
        provider="together",
        context_window=131072,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="venice/claude-opus-45",
        name="Venice Claude Opus 4.5",
        provider="venice",
        context_window=202000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning", "vision", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="huggingface/deepseek-ai/DeepSeek-R1",
        name="HuggingFace DeepSeek R1",
        provider="huggingface",
        context_window=131072,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="huggingface/deepseek-ai/DeepSeek-V3.1",
        name="HuggingFace DeepSeek V3.1",
        provider="huggingface",
        context_window=131072,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="huggingface/openai/gpt-oss-120b",
        name="HuggingFace GPT OSS 120B",
        provider="huggingface",
        context_window=131072,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="qianfan/deepseek-v3.2",
        name="Qianfan DeepSeek V3.2",
        provider="qianfan",
        context_window=98304,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="qianfan/ernie-5.0-thinking-preview",
        name="Qianfan ERNIE 5.0 Thinking Preview",
        provider="qianfan",
        context_window=119000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning", "vision", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="nvidia/nvidia/llama-3.1-nemotron-70b-instruct",
        name="NVIDIA Nemotron 70B Instruct",
        provider="nvidia",
        context_window=131072,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="nvidia/meta/llama-3.3-70b-instruct",
        name="NVIDIA Meta Llama 3.3 70B",
        provider="nvidia",
        context_window=131072,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="nvidia/nvidia/mistral-nemo-minitron-8b-8k-instruct",
        name="NVIDIA Mistral NeMo Minitron 8B",
        provider="nvidia",
        context_window=8192,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="opencode/claude-opus-4-6",
        name="OpenCode Claude Opus 4.6",
        provider="opencode",
        context_window=200000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning", "vision", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="xai/grok-4.1-mini",
        name="xAI Grok 4.1 Mini",
        provider="xai",
        context_window=256000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["reasoning", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="cerebras/zai-glm-4.7",
        name="Cerebras GLM 4.7",
        provider="cerebras",
        context_window=128000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="xiaomi/mimo-v2-flash",
        name="Xiaomi MiMo V2 Flash",
        provider="xiaomi",
        context_window=262144,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="volcengine/doubao-seed-1-8-251228",
        name="Volcano Engine Doubao Seed 1.8",
        provider="volcengine",
        context_window=256000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="volcengine/kimi-k2-5-260127",
        name="Volcano Engine Kimi K2.5",
        provider="volcengine",
        context_window=256000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="byteplus/seed-1-8-251228",
        name="BytePlus Seed 1.8",
        provider="byteplus",
        context_window=256000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "chat"],
        is_premium=True
    ),
    ModelMetadata(
        id="byteplus/kimi-k2-5-260127",
        name="BytePlus Kimi K2.5",
        provider="byteplus",
        context_window=256000,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["vision", "chat"],
        is_premium=True
    ),

    # --- Groq ---
    ModelMetadata(
        id="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        name="Groq Llama 4 Scout 17B",
        provider="groq",
        context_window=131072,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat", "fast"],
        is_premium=True
    ),
    ModelMetadata(
        id="groq/llama3-70b-8192",
        name="Groq Llama 3 70B",
        provider="groq",
        context_window=8192,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0), # Free usually
        capabilities=["chat", "fast"],
        is_premium=True
    ),
    ModelMetadata(
        id="groq/mixtral-8x7b-32768",
        name="Groq Mixtral",
        provider="groq",
        context_window=32768,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat", "fast"],
        is_premium=True
    ),
    ModelMetadata(
        id="groq/gemma2-9b-it",
        name="Groq Gemma 2 9B",
        provider="groq",
        context_window=8192,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=["chat", "fast"],
        is_premium=True
    )
]


def _parity_model(
    model_id: str,
    name: str,
    context_window: int = 128000,
    capabilities: list[str] | None = None,
) -> ModelMetadata:
    return ModelMetadata(
        id=model_id,
        name=name,
        provider=model_id.split("/", 1)[0],
        context_window=context_window,
        pricing=ModelPricing(input_1m=0.0, output_1m=0.0),
        capabilities=capabilities or ["chat"],
        is_premium=True,
    )


# Kabot parity additions not covered by the base static catalog above.
KABOT_PARITY_MODELS = [
    # OpenRouter references (dynamic catalog provider; curated defaults + common refs)
    _parity_model("openrouter/auto", "OpenRouter Auto", 200000, ["chat", "vision", "tools"]),
    _parity_model(
        "openrouter/anthropic/claude-sonnet-4-5",
        "OpenRouter Claude Sonnet 4.5",
        200000,
        ["reasoning", "vision", "chat"],
    ),
    _parity_model(
        "openrouter/anthropic/claude-opus-4-5",
        "OpenRouter Claude Opus 4.5",
        200000,
        ["reasoning", "vision", "chat"],
    ),
    _parity_model("openrouter/deepseek/deepseek-r1", "OpenRouter DeepSeek R1", 131072, ["reasoning", "chat"]),
    _parity_model("openrouter/deepseek-chat", "OpenRouter DeepSeek Chat", 128000, ["chat"]),
    _parity_model(
        "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "OpenRouter Llama 3.3 70B Instruct Free",
        131072,
        ["chat"],
    ),
    _parity_model(
        "openrouter/meta-llama/llama-3.3-70b:free",
        "OpenRouter Llama 3.3 70B Free",
        131072,
        ["chat"],
    ),
    _parity_model(
        "openrouter/qwen/qwen-2.5-vl-72b-instruct:free",
        "OpenRouter Qwen 2.5 VL 72B Free",
        131072,
        ["vision", "chat"],
    ),
    _parity_model(
        "openrouter/google/gemini-2.0-flash-vision:free",
        "OpenRouter Gemini 2.0 Flash Vision Free",
        1048576,
        ["vision", "chat"],
    ),
    _parity_model(
        "openrouter/google/gemini-3.1-pro",
        "OpenRouter Gemini 3.1 Pro",
        2000000,
        ["vision", "reasoning", "chat"],
    ),
    _parity_model("openrouter/minimax/minimax-m2.5", "OpenRouter MiniMax M2.5", 200000, ["reasoning", "chat"]),
    _parity_model("openrouter/moonshotai/kimi-k2", "OpenRouter Kimi K2", 262144, ["chat"]),
    _parity_model("openrouter/moonshotai/kimi-k2.5", "OpenRouter Kimi K2.5", 262144, ["reasoning", "chat"]),
    _parity_model("openrouter/x-ai/grok-4.1-fast", "OpenRouter Grok 4.1 Fast", 256000, ["reasoning", "chat"]),

    # Together
    _parity_model("together/zai-org/GLM-4.7", "Together GLM 4.7 Fp8", 202752),
    _parity_model(
        "together/meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "Together Llama 3.3 70B Instruct Turbo",
        131072,
    ),
    _parity_model(
        "together/meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "Together Llama 4 Maverick 17B",
        20000000,
        ["vision", "chat"],
    ),
    _parity_model("together/deepseek-ai/DeepSeek-V3.1", "Together DeepSeek V3.1", 131072),
    _parity_model(
        "together/moonshotai/Kimi-K2-Instruct-0905",
        "Together Kimi K2 Instruct 0905",
        262144,
    ),

    # Venice
    _parity_model("venice/llama-3.2-3b", "Venice Llama 3.2 3B", 131072),
    _parity_model("venice/hermes-3-llama-3.1-405b", "Venice Hermes 3 Llama 3.1 405B", 131072),
    _parity_model(
        "venice/qwen3-235b-a22b-thinking-2507",
        "Venice Qwen3 235B Thinking",
        131072,
        ["reasoning", "chat"],
    ),
    _parity_model("venice/qwen3-235b-a22b-instruct-2507", "Venice Qwen3 235B Instruct", 131072),
    _parity_model(
        "venice/qwen3-coder-480b-a35b-instruct",
        "Venice Qwen3 Coder 480B",
        262144,
        ["coding", "chat"],
    ),
    _parity_model("venice/qwen3-next-80b", "Venice Qwen3 Next 80B", 262144),
    _parity_model("venice/qwen3-vl-235b-a22b", "Venice Qwen3 VL 235B", 262144, ["vision", "chat"]),
    _parity_model("venice/qwen3-4b", "Venice Qwen3 4B", 32768, ["reasoning", "chat"]),
    _parity_model("venice/deepseek-v3.2", "Venice DeepSeek V3.2", 163840, ["reasoning", "chat"]),
    _parity_model("venice/venice-uncensored", "Venice Uncensored", 32768),
    _parity_model("venice/mistral-31-24b", "Venice Mistral 31 24B", 131072, ["vision", "chat"]),
    _parity_model(
        "venice/google-gemma-3-27b-it",
        "Venice Gemma 3 27B Instruct",
        202752,
        ["vision", "chat"],
    ),
    _parity_model("venice/openai-gpt-oss-120b", "Venice GPT OSS 120B", 131072),
    _parity_model("venice/zai-org-glm-4.7", "Venice GLM 4.7", 202752, ["reasoning", "chat"]),
    _parity_model("venice/claude-sonnet-45", "Venice Claude Sonnet 4.5", 202752, ["reasoning", "vision", "chat"]),
    _parity_model("venice/openai-gpt-52", "Venice GPT 5.2", 262144, ["reasoning", "chat"]),
    _parity_model(
        "venice/openai-gpt-52-codex",
        "Venice GPT 5.2 Codex",
        262144,
        ["reasoning", "vision", "coding"],
    ),
    _parity_model("venice/gemini-3-pro-preview", "Venice Gemini 3 Pro Preview", 202752, ["reasoning", "vision", "chat"]),
    _parity_model(
        "venice/gemini-3-flash-preview",
        "Venice Gemini 3 Flash Preview",
        262144,
        ["reasoning", "vision", "chat"],
    ),
    _parity_model("venice/grok-41-fast", "Venice Grok 4.1 Fast", 262144, ["reasoning", "vision", "chat"]),
    _parity_model("venice/grok-code-fast-1", "Venice Grok Code Fast 1", 262144, ["reasoning", "coding"]),
    _parity_model("venice/kimi-k2-thinking", "Venice Kimi K2 Thinking", 262144, ["reasoning", "chat"]),
    _parity_model("venice/minimax-m21", "Venice MiniMax M2.1", 202752, ["reasoning", "chat"]),

    # HuggingFace static + docs variants
    _parity_model(
        "huggingface/meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "HuggingFace Llama 3.3 70B Instruct Turbo",
        131072,
    ),
    _parity_model("huggingface/deepseek-ai/DeepSeek-V3.2", "HuggingFace DeepSeek V3.2", 131072),
    _parity_model("huggingface/Qwen/Qwen3-8B", "HuggingFace Qwen3 8B", 131072),
    _parity_model("huggingface/Qwen/Qwen2.5-7B-Instruct", "HuggingFace Qwen2.5 7B Instruct", 131072),
    _parity_model("huggingface/meta-llama/Llama-3.3-70B-Instruct", "HuggingFace Llama 3.3 70B Instruct", 131072),
    _parity_model("huggingface/meta-llama/Llama-3.1-8B-Instruct", "HuggingFace Llama 3.1 8B Instruct", 131072),

    # Kilo Gateway
    _parity_model("kilocode/z-ai/glm-5:free", "Kilo GLM 5 Free", 202800, ["reasoning", "chat"]),
    _parity_model("kilocode/minimax/minimax-m2.5:free", "Kilo MiniMax M2.5 Free", 204800, ["reasoning", "chat"]),
    _parity_model("kilocode/anthropic/claude-sonnet-4.5", "Kilo Claude Sonnet 4.5", 1000000, ["reasoning", "vision", "chat"]),
    _parity_model("kilocode/google/gemini-3-pro-preview", "Kilo Gemini 3 Pro Preview", 1048576, ["reasoning", "vision", "chat"]),
    _parity_model(
        "kilocode/google/gemini-3-flash-preview",
        "Kilo Gemini 3 Flash Preview",
        1048576,
        ["reasoning", "vision", "chat"],
    ),
    _parity_model("kilocode/x-ai/grok-code-fast-1", "Kilo Grok Code Fast 1", 256000, ["reasoning", "coding"]),
    _parity_model("kilocode/moonshotai/kimi-k2.5", "Kilo Kimi K2.5", 262144, ["reasoning", "vision", "chat"]),

    # Moonshot / Kimi
    _parity_model("moonshot/kimi-k2-0905-preview", "Kimi K2 0905 Preview", 256000),
    _parity_model("moonshot/kimi-k2-thinking-turbo", "Kimi K2 Thinking Turbo", 128000, ["reasoning", "chat"]),

    # MiniMax
    _parity_model("minimax/MiniMax-VL-01", "MiniMax VL 01", 200000, ["vision", "chat"]),
    _parity_model("minimax/MiniMax-M2.5", "MiniMax M2.5", 200000, ["reasoning", "chat"]),
    _parity_model("minimax/MiniMax-M2.5-Lightning", "MiniMax M2.5 Lightning", 200000, ["reasoning", "chat"]),

    # NVIDIA compatibility ids
    _parity_model("nvidia/llama-3.1-nemotron-70b-instruct", "NVIDIA Llama 3.1 Nemotron 70B", 131072),
    _parity_model("nvidia/mistral-nemo-minitron-8b-8k-instruct", "NVIDIA Mistral NeMo Minitron 8B", 8192),

    # OpenCode Zen full static fallback set
    _parity_model("opencode/gpt-5.1-codex", "OpenCode GPT 5.1 Codex", 400000, ["reasoning", "coding"]),
    _parity_model("opencode/claude-opus-4-5", "OpenCode Claude Opus 4.5", 200000, ["reasoning", "vision", "chat"]),
    _parity_model("opencode/gemini-3-pro", "OpenCode Gemini 3 Pro", 1048576, ["reasoning", "vision", "chat"]),
    _parity_model("opencode/gpt-5.1-codex-mini", "OpenCode GPT 5.1 Codex Mini", 400000, ["reasoning", "coding"]),
    _parity_model("opencode/gpt-5.1", "OpenCode GPT 5.1", 400000, ["reasoning", "chat"]),
    _parity_model("opencode/glm-4.7", "OpenCode GLM 4.7", 204800),
    _parity_model("opencode/gemini-3-flash", "OpenCode Gemini 3 Flash", 1048576, ["reasoning", "vision", "chat"]),
    _parity_model("opencode/gpt-5.1-codex-max", "OpenCode GPT 5.1 Codex Max", 400000, ["reasoning", "coding"]),
    _parity_model("opencode/gpt-5.2", "OpenCode GPT 5.2", 400000, ["reasoning", "chat"]),

    # Volcengine
    _parity_model("volcengine/doubao-seed-code-preview-251028", "Volcengine Doubao Seed Code Preview", 256000, ["vision", "coding"]),
    _parity_model("volcengine/glm-4-7-251222", "Volcengine GLM 4.7", 200000, ["vision", "chat"]),
    _parity_model("volcengine/deepseek-v3-2-251201", "Volcengine DeepSeek V3.2", 128000, ["chat"]),
    _parity_model("volcengine-plan/ark-code-latest", "Volcengine Ark Code Latest", 256000, ["coding", "chat"]),
    _parity_model("volcengine-plan/doubao-seed-code", "Volcengine Doubao Seed Code", 256000, ["coding", "chat"]),
    _parity_model("volcengine-plan/glm-4.7", "Volcengine GLM 4.7 Coding", 200000, ["coding", "chat"]),
    _parity_model("volcengine-plan/kimi-k2-thinking", "Volcengine Kimi K2 Thinking", 256000, ["coding", "reasoning"]),
    _parity_model("volcengine-plan/kimi-k2.5", "Volcengine Kimi K2.5 Coding", 256000, ["coding", "chat"]),
    _parity_model(
        "volcengine-plan/doubao-seed-code-preview-251028",
        "Volcengine Doubao Seed Code Preview",
        256000,
        ["coding", "chat"],
    ),

    # BytePlus
    _parity_model("byteplus/glm-4-7-251222", "BytePlus GLM 4.7", 200000, ["vision", "chat"]),
    _parity_model("byteplus-plan/ark-code-latest", "BytePlus Ark Code Latest", 256000, ["coding", "chat"]),
    _parity_model("byteplus-plan/doubao-seed-code", "BytePlus Doubao Seed Code", 256000, ["coding", "chat"]),
    _parity_model("byteplus-plan/glm-4.7", "BytePlus GLM 4.7 Coding", 200000, ["coding", "chat"]),
    _parity_model("byteplus-plan/kimi-k2-thinking", "BytePlus Kimi K2 Thinking", 256000, ["coding", "reasoning"]),
    _parity_model("byteplus-plan/kimi-k2.5", "BytePlus Kimi K2.5 Coding", 256000, ["coding", "chat"]),

    # Synthetic
    _parity_model("synthetic/hf:MiniMaxAI/MiniMax-M2.1", "Synthetic MiniMax M2.1", 192000),
    _parity_model("synthetic/hf:moonshotai/Kimi-K2-Thinking", "Synthetic Kimi K2 Thinking", 256000, ["reasoning", "chat"]),
    _parity_model("synthetic/hf:zai-org/GLM-4.7", "Synthetic GLM 4.7", 198000),
    _parity_model("synthetic/hf:deepseek-ai/DeepSeek-R1-0528", "Synthetic DeepSeek R1 0528", 128000, ["reasoning", "chat"]),
    _parity_model("synthetic/hf:deepseek-ai/DeepSeek-V3-0324", "Synthetic DeepSeek V3 0324", 128000),
    _parity_model("synthetic/hf:deepseek-ai/DeepSeek-V3.1", "Synthetic DeepSeek V3.1", 128000),
    _parity_model("synthetic/hf:deepseek-ai/DeepSeek-V3.1-Terminus", "Synthetic DeepSeek V3.1 Terminus", 128000),
    _parity_model("synthetic/hf:deepseek-ai/DeepSeek-V3.2", "Synthetic DeepSeek V3.2", 159000),
    _parity_model("synthetic/hf:meta-llama/Llama-3.3-70B-Instruct", "Synthetic Llama 3.3 70B Instruct", 128000),
    _parity_model(
        "synthetic/hf:meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        "Synthetic Llama 4 Maverick 17B",
        524000,
    ),
    _parity_model("synthetic/hf:moonshotai/Kimi-K2-Instruct-0905", "Synthetic Kimi K2 Instruct 0905", 256000),
    _parity_model("synthetic/hf:moonshotai/Kimi-K2.5", "Synthetic Kimi K2.5", 256000, ["vision", "chat"]),
    _parity_model("synthetic/hf:openai/gpt-oss-120b", "Synthetic GPT OSS 120B", 128000),
    _parity_model("synthetic/hf:Qwen/Qwen3-235B-A22B-Instruct-2507", "Synthetic Qwen3 235B Instruct", 256000),
    _parity_model("synthetic/hf:Qwen/Qwen3-Coder-480B-A35B-Instruct", "Synthetic Qwen3 Coder 480B", 256000, ["coding", "chat"]),
    _parity_model("synthetic/hf:Qwen/Qwen3-VL-235B-A22B-Instruct", "Synthetic Qwen3 VL 235B", 250000, ["vision", "chat"]),
    _parity_model("synthetic/hf:zai-org/GLM-4.5", "Synthetic GLM 4.5", 128000),
    _parity_model("synthetic/hf:zai-org/GLM-4.6", "Synthetic GLM 4.6", 198000),
    _parity_model("synthetic/hf:zai-org/GLM-5", "Synthetic GLM 5", 256000, ["vision", "reasoning", "chat"]),
    _parity_model("synthetic/hf:deepseek-ai/DeepSeek-V3", "Synthetic DeepSeek V3", 128000),
    _parity_model(
        "synthetic/hf:Qwen/Qwen3-235B-A22B-Thinking-2507",
        "Synthetic Qwen3 235B Thinking",
        256000,
        ["reasoning", "chat"],
    ),

    # Gateway providers
    _parity_model("cloudflare-ai-gateway/claude-sonnet-4-5", "Cloudflare AI Gateway Claude Sonnet 4.5", 200000, ["reasoning", "vision", "chat"]),
    _parity_model(
        "vercel-ai-gateway/anthropic/claude-opus-4.6",
        "Vercel AI Gateway Claude Opus 4.6",
        200000,
        ["reasoning", "vision", "chat"],
    ),
    _parity_model(
        "vercel-ai-gateway/anthropic/claude-opus-4-6",
        "Vercel AI Gateway Claude Opus 4.6",
        200000,
        ["reasoning", "vision", "chat"],
    ),
    _parity_model(
        "vercel-ai-gateway/claude-opus-4.6",
        "Vercel AI Gateway Claude Opus 4.6 (Shorthand)",
        200000,
        ["reasoning", "vision", "chat"],
    ),
    _parity_model(
        "vercel-ai-gateway/opus-4.6",
        "Vercel AI Gateway Opus 4.6 (Shorthand)",
        200000,
        ["reasoning", "vision", "chat"],
    ),
]

_existing_catalog_ids = {model.id for model in STATIC_MODEL_CATALOG}
for model in KABOT_PARITY_MODELS:
    if model.id not in _existing_catalog_ids:
        STATIC_MODEL_CATALOG.append(model)
        _existing_catalog_ids.add(model.id)

def populate_registry(registry):
    """Populate the registry with the static catalog."""
    for metadata in STATIC_MODEL_CATALOG:
        registry.register(metadata)

    # Register common aliases matching Kabot's model-reference
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
    registry.register_alias("gemini31", "google/gemini-3.1-pro")
    registry.register_alias("gemini-3.1-pro", "google/gemini-3.1-pro")
    registry.register_alias("mistral", "mistral/mistral-large-latest")

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
    registry.register_alias("venice-opus", "venice/claude-opus-45")
    registry.register_alias("together-kimi", "together/moonshotai/Kimi-K2.5")
    registry.register_alias("kilo", "kilocode/anthropic/claude-opus-4.6")
    registry.register_alias("hf-r1", "huggingface/deepseek-ai/DeepSeek-R1")
    registry.register_alias("qianfan", "qianfan/deepseek-v3.2")
    registry.register_alias("nvidia", "nvidia/nvidia/llama-3.1-nemotron-70b-instruct")
    registry.register_alias("opencode", "opencode/claude-opus-4-6")
    registry.register_alias("xai", "xai/grok-4.1-mini")
    registry.register_alias("cerebras", "cerebras/zai-glm-4.7")
    registry.register_alias("xiaomi", "xiaomi/mimo-v2-flash")
    registry.register_alias("doubao", "volcengine/doubao-seed-1-8-251228")
    registry.register_alias("byteplus", "byteplus/seed-1-8-251228")
    registry.register_alias("openrouter", "openrouter/auto")
    registry.register_alias("or-auto", "openrouter/auto")
    registry.register_alias("or-sonnet", "openrouter/anthropic/claude-sonnet-4-5")
    registry.register_alias("or-qwen-vl", "openrouter/qwen/qwen-2.5-vl-72b-instruct:free")
    registry.register_alias("synthetic", "synthetic/hf:MiniMaxAI/MiniMax-M2.1")
    registry.register_alias("cf-sonnet", "cloudflare-ai-gateway/claude-sonnet-4-5")
    registry.register_alias("vercel-opus", "vercel-ai-gateway/anthropic/claude-opus-4.6")


