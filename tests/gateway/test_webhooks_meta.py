"""Tests for Meta webhook verification and ingress."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def _meta_sig(secret: str, raw: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.mark.asyncio
async def test_meta_webhook_verification_challenge(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    server = WebhookServer(bus=bus, meta_verify_token="verify-me", meta_app_secret="secret")
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/webhooks/meta?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=123"
    )
    assert resp.status == 200
    assert await resp.text() == "123"


@pytest.mark.asyncio
async def test_meta_webhook_rejects_invalid_signature(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    server = WebhookServer(bus=bus, meta_verify_token="verify-me", meta_app_secret="secret")
    client = await aiohttp_client(server.app)

    payload = {"entry": [{"changes": [{"field": "threads", "value": {"text": "hello"}}]}]}
    resp = await client.post(
        "/webhooks/meta",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid",
        },
    )
    assert resp.status == 401


@pytest.mark.asyncio
async def test_meta_webhook_accepts_valid_signature_and_publishes(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    secret = "secret"
    server = WebhookServer(bus=bus, meta_verify_token="verify-me", meta_app_secret=secret)
    client = await aiohttp_client(server.app)

    payload = {
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "field": "threads",
                        "value": {
                            "thread_id": "thread-1",
                            "text": "hello meta",
                            "from": {"id": "user-1"},
                        },
                    }
                ],
            }
        ]
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = await client.post(
        "/webhooks/meta",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _meta_sig(secret, raw),
        },
    )
    assert resp.status == 202
    bus.publish_inbound.assert_awaited_once()
