"""Tests for cron webhook POST helper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kabot.cron.service import _deliver_webhook


class TestWebhookPost:
    @pytest.mark.asyncio
    async def test_webhook_post_success(self):
        with patch("kabot.cron.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await _deliver_webhook(
                url="https://example.com/hook",
                job_id="j1",
                job_name="Test",
                output="Hello",
                secret="mysecret",
            )

            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_post_hmac_header(self):
        with patch("kabot.cron.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            await _deliver_webhook(
                url="https://x.com/h",
                job_id="j1",
                job_name="t",
                output="o",
                secret="sec",
            )

            call_kwargs = mock_client.post.call_args.kwargs
            headers = call_kwargs.get("headers", {})
            assert "X-Kabot-Signature" in headers
