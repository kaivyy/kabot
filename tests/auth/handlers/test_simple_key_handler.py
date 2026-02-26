from unittest.mock import patch

from kabot.auth.handlers.simple import SimpleKeyHandler


@patch.dict("os.environ", {}, clear=True)
@patch("kabot.auth.handlers.simple.Prompt.ask")
def test_simple_key_handler_uses_visible_prompt_for_api_key(mock_ask):
    mock_ask.return_value = "test-key-1234567890"

    handler = SimpleKeyHandler(
        provider_id="groq",
        provider_name="Groq",
        env_var="GROQ_API_KEY",
        help_url="https://console.groq.com/keys",
    )
    result = handler.authenticate()

    mock_ask.assert_called_once()
    assert mock_ask.call_args.kwargs.get("password") is False
    assert result == {"providers": {"groq": {"api_key": "test-key-1234567890"}}}
