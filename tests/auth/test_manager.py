"""Tests for AuthManager with multi-method support."""
from unittest.mock import MagicMock, patch


def test_auth_manager_exists():
    """AuthManager class should exist."""
    from kabot.auth.manager import AuthManager
    assert AuthManager is not None


def test_list_providers_returns_list():
    """list_providers should return list of provider IDs."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    providers = manager.list_providers()
    assert isinstance(providers, list)
    assert "openai" in providers
    assert "anthropic" in providers


def test_load_handler_dynamically():
    """_load_handler should load handler class from string path."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    handler = manager._load_handler("openai", "api_key")
    assert handler is not None
    assert handler.name == "OpenAI (API Key)"


def test_login_with_invalid_provider():
    """login with invalid provider should return False."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("invalid_provider")
    assert result is False


def test_login_with_invalid_method():
    """login with invalid method should return False."""
    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("openai", method_id="invalid_method")
    assert result is False


@patch('kabot.auth.manager.AuthManager._load_handler')
@patch('kabot.auth.manager.AuthManager._save_credentials')
def test_login_with_method_specified(mock_save, mock_load):
    """login with method_id should skip menu and use specified method."""
    mock_handler = MagicMock()
    mock_handler.authenticate.return_value = {"providers": {"openai": {"api_key": "test"}}}
    mock_load.return_value = mock_handler
    mock_save.return_value = True

    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("openai", method_id="api_key")

    mock_load.assert_called_once_with("openai", "api_key")
    assert result is True


@patch('kabot.auth.manager.AuthManager._load_handler')
@patch('kabot.auth.manager.AuthManager._save_credentials')
def test_login_alias_openai_codex_defaults_to_oauth(mock_save, mock_load):
    """openai-codex alias should map to openai provider with oauth default."""
    mock_handler = MagicMock()
    mock_handler.authenticate.return_value = {"providers": {"openai_codex": {"oauth_token": "tok"}}}
    mock_load.return_value = mock_handler
    mock_save.return_value = True

    from kabot.auth.manager import AuthManager
    manager = AuthManager()

    result = manager.login("openai-codex")

    mock_load.assert_called_once_with("openai", "oauth")
    assert result is True


@patch('kabot.auth.manager.AuthManager._load_handler')
@patch('kabot.auth.manager.AuthManager._save_credentials')
def test_login_alias_moonshot_maps_to_kimi(mock_save, mock_load):
    """moonshot alias should map to kimi provider."""
    mock_handler = MagicMock()
    mock_handler.authenticate.return_value = {"providers": {"moonshot": {"api_key": "test"}}}
    mock_load.return_value = mock_handler
    mock_save.return_value = True

    from kabot.auth.manager import AuthManager
    manager = AuthManager()

    result = manager.login("moonshot", method_id="api_key")

    mock_load.assert_called_once_with("kimi", "api_key")
    assert result is True


@patch('kabot.auth.manager.AuthManager._load_handler')
@patch('kabot.auth.manager.AuthManager._save_credentials')
def test_login_alias_gemini_maps_to_google(mock_save, mock_load):
    """gemini alias should map to google provider."""
    mock_handler = MagicMock()
    mock_handler.authenticate.return_value = {"providers": {"gemini": {"api_key": "test"}}}
    mock_load.return_value = mock_handler
    mock_save.return_value = True

    from kabot.auth.manager import AuthManager
    manager = AuthManager()

    result = manager.login("gemini", method_id="api_key")

    mock_load.assert_called_once_with("google", "api_key")
    assert result is True


@patch('kabot.auth.manager.AuthManager._load_handler')
@patch('kabot.auth.manager.AuthManager._save_credentials')
def test_login_alias_vllm_maps_to_ollama(mock_save, mock_load):
    """vllm alias should map to ollama provider."""
    mock_handler = MagicMock()
    mock_handler.authenticate.return_value = {"providers": {"vllm": {"api_base": "http://localhost:11434"}}}
    mock_load.return_value = mock_handler
    mock_save.return_value = True

    from kabot.auth.manager import AuthManager
    manager = AuthManager()

    result = manager.login("vllm", method_id="url")

    mock_load.assert_called_once_with("ollama", "url")
    assert result is True


def test_validate_auth_data_accepts_setup_token():
    """setup_token payload should be recognized as valid auth data."""
    from kabot.auth.manager import AuthManager

    manager = AuthManager()
    auth_data = {"providers": {"anthropic": {"setup_token": "sk-ant-oat01-example"}}}
    assert manager._validate_auth_data(auth_data) is True


@patch('kabot.auth.manager.AuthManager._load_handler')
def test_login_handles_keyboard_interrupt(mock_load):
    """login should handle KeyboardInterrupt gracefully."""
    mock_handler = MagicMock()
    mock_handler.authenticate.side_effect = KeyboardInterrupt()
    mock_load.return_value = mock_handler

    from kabot.auth.manager import AuthManager
    manager = AuthManager()
    result = manager.login("openai", method_id="api_key")

    assert result is False
