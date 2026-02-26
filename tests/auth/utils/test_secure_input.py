from unittest.mock import patch

from kabot.auth.utils import secure_input


def test_secure_input_returns_hidden_prompt_value():
    with patch("kabot.auth.utils.Prompt.ask", return_value="  gsk_test  ") as ask_mock:
        value = secure_input("Enter API key")

    assert value == "gsk_test"
    ask_mock.assert_called_once_with("Enter API key", password=True)


def test_secure_input_falls_back_to_visible_when_hidden_prompt_fails():
    with patch(
        "kabot.auth.utils.Prompt.ask",
        side_effect=[EOFError("stdin issue"), "gsk_visible"],
    ) as ask_mock:
        value = secure_input("Enter API key")

    assert value == "gsk_visible"
    assert ask_mock.call_count == 2
    first_call = ask_mock.call_args_list[0]
    second_call = ask_mock.call_args_list[1]
    assert first_call.kwargs["password"] is True
    assert second_call.kwargs["password"] is False
