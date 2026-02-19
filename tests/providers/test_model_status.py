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


# Tests for get_status_indicator
def test_get_status_indicator_working():
    assert get_status_indicator("working") == "✓"


def test_get_status_indicator_catalog():
    assert get_status_indicator("catalog") == "⚠"


def test_get_status_indicator_unsupported():
    assert get_status_indicator("unsupported") == "✗"


def test_get_status_indicator_unknown():
    assert get_status_indicator("unknown") == "?"
