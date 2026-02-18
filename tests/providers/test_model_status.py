def test_get_model_status_working():
    from kabot.providers.model_status import get_model_status
    assert get_model_status("openai/gpt-4o") == "working"

def test_get_model_status_catalog():
    from kabot.providers.model_status import get_model_status
    assert get_model_status("openai/gpt-5.1-codex") == "catalog"

def test_get_model_status_unsupported():
    from kabot.providers.model_status import get_model_status
    assert get_model_status("openai-codex/gpt-5.3-codex") == "unsupported"
