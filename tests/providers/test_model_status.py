from kabot.providers.model_status import get_model_status, get_status_indicator


# Tests for get_model_status
def test_get_model_status_working():
    assert get_model_status("openai/gpt-4o") == "working"


def test_get_model_status_catalog():
    assert get_model_status("openai/gpt-5.1-codex") == "catalog"


def test_get_model_status_unsupported():
    assert get_model_status("openai-codex/gpt-5.3-codex") in {"catalog", "working"}


def test_get_model_status_unknown():
    assert get_model_status("random-provider/random-model") == "unknown"


def test_get_model_status_catalog_from_unsupported_provider():
    """Test that catalog models from unsupported providers return 'catalog' not 'unsupported'."""
    assert get_model_status("google-gemini-cli/gemini-3-pro-preview") == "catalog"


def test_get_model_status_codex_spark_catalog():
    assert get_model_status("openai-codex/gpt-5.3-codex-spark") in {"catalog", "working"}


# Edge case tests
def test_get_model_status_none():
    assert get_model_status(None) == "unknown"


def test_get_model_status_empty_string():
    assert get_model_status("") == "unknown"


def test_get_model_status_no_separator():
    """Test model ID without '/' separator."""
    assert get_model_status("openai-codex") in {"catalog", "working", "unknown"}


def test_get_model_status_qwen_portal_catalog():
    assert get_model_status("qwen-portal/coder-model") in {"catalog", "working"}


def test_get_model_status_mistral_catalog():
    assert get_model_status("mistral/mistral-large-latest") in {"catalog", "working"}


def test_get_model_status_kilocode_catalog():
    assert get_model_status("kilocode/anthropic/claude-opus-4.6") in {"catalog", "working"}


def test_get_model_status_together_catalog():
    assert get_model_status("together/moonshotai/Kimi-K2.5") in {"catalog", "working"}


def test_get_model_status_venice_catalog():
    assert get_model_status("venice/llama-3.3-70b") in {"catalog", "working"}


def test_get_model_status_huggingface_catalog():
    assert get_model_status("huggingface/deepseek-ai/DeepSeek-R1") in {"catalog", "working"}


def test_get_model_status_openrouter_catalog():
    assert get_model_status("openrouter/auto") in {"catalog", "working"}


# Extended parity coverage
def test_get_model_status_venice_extended_catalog():
    assert get_model_status("venice/qwen3-coder-480b-a35b-instruct") in {"catalog", "working"}


def test_get_model_status_opencode_extended_catalog():
    assert get_model_status("opencode/gpt-5.2") in {"catalog", "working"}


def test_get_model_status_kilocode_extended_catalog():
    assert get_model_status("kilocode/z-ai/glm-5:free") in {"catalog", "working"}


def test_get_model_status_synthetic_catalog():
    assert get_model_status("synthetic/hf:MiniMaxAI/MiniMax-M2.1") in {"catalog", "working"}


def test_get_model_status_gateway_catalog_refs():
    assert get_model_status("vercel-ai-gateway/anthropic/claude-opus-4.6") in {"catalog", "working"}
    assert get_model_status("cloudflare-ai-gateway/claude-sonnet-4-5") in {"catalog", "working"}


# Tests for get_status_indicator
def test_get_status_indicator_working():
    assert get_status_indicator("working") == "OK"


def test_get_status_indicator_catalog():
    assert get_status_indicator("catalog") == "!"


def test_get_status_indicator_unsupported():
    assert get_status_indicator("unsupported") == "X"


def test_get_status_indicator_unknown():
    assert get_status_indicator("unknown") == "?"

