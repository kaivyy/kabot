"""Tests for multi-method auth menu structure."""


def test_auth_providers_has_methods_dict():
    """AUTH_PROVIDERS should have 'methods' dict instead of 'handler'."""
    from kabot.auth.menu import AUTH_PROVIDERS

    for provider_id, provider_info in AUTH_PROVIDERS.items():
        assert "methods" in provider_info, f"{provider_id} missing 'methods' key"
        assert isinstance(provider_info["methods"], dict), f"{provider_id} 'methods' should be dict"
        assert len(provider_info["methods"]) >= 1, f"{provider_id} should have at least 1 method"


def test_each_method_has_required_fields():
    """Each method should have label, description, handler."""
    from kabot.auth.menu import AUTH_PROVIDERS

    required_fields = {"label", "description", "handler"}

    for provider_id, provider_info in AUTH_PROVIDERS.items():
        for method_id, method_info in provider_info["methods"].items():
            for field in required_fields:
                assert field in method_info, f"{provider_id}.{method_id} missing '{field}'"


def test_handler_paths_are_strings():
    """Handler should be string path for lazy loading."""
    from kabot.auth.menu import AUTH_PROVIDERS

    for provider_id, provider_info in AUTH_PROVIDERS.items():
        for method_id, method_info in provider_info["methods"].items():
            handler = method_info["handler"]
            assert isinstance(handler, str), f"{provider_id}.{method_id} handler should be string path"
            assert "." in handler, f"{provider_id}.{method_id} handler should be module.Class path"


def test_get_auth_choices_returns_list():
    """get_auth_choices should return list of provider choices."""
    from kabot.auth.menu import get_auth_choices

    choices = get_auth_choices()
    assert isinstance(choices, list)
    assert len(choices) >= 4  # At least 4 providers


def test_get_method_choices_returns_list():
    """get_method_choices should return list of method choices for provider."""
    from kabot.auth.menu import get_method_choices

    choices = get_method_choices("openai")
    assert isinstance(choices, list)
    assert len(choices) >= 1

    # Each choice should have id, label, description
    for choice in choices:
        assert "id" in choice
        assert "label" in choice
        assert "description" in choice
