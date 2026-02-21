"""Tests for Telegram inline button support."""

from kabot.channels.telegram import build_inline_keyboard


class TestBuildInlineKeyboard:
    def test_single_row(self):
        buttons = [{"text": "Yes", "callback_data": "yes"}, {"text": "No", "callback_data": "no"}]
        markup = build_inline_keyboard([buttons])
        assert markup is not None
        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 2

    def test_multiple_rows(self):
        rows = [
            [{"text": "A", "callback_data": "a"}],
            [{"text": "B", "callback_data": "b"}],
        ]
        markup = build_inline_keyboard(rows)
        assert markup is not None
        assert len(markup.inline_keyboard) == 2

    def test_url_button(self):
        buttons = [{"text": "Visit", "url": "https://example.com"}]
        markup = build_inline_keyboard([buttons])
        assert markup is not None
        assert markup.inline_keyboard[0][0].url == "https://example.com"

    def test_empty_returns_none(self):
        assert build_inline_keyboard([]) is None
