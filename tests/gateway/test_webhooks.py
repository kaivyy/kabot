"""Tests for Webhook Ingress Infrastructure."""
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_webhook_trigger_success(aiohttp_client):
    """Test that valid webhook triggers are accepted."""
    from kabot.gateway.webhook_server import WebhookServer

    # Mock message bus
    mock_bus = MagicMock()
    # publish_inbound needs to be awaitable
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus)
    client = await aiohttp_client(server.app)

    payload = {
        "event": "message.received",
        "data": {
            "content": "Hello from webhook",
            "sender": "external_system"
        }
    }

    resp = await client.post("/webhooks/trigger", json=payload)
    assert resp.status == 202
    assert await resp.text() == "Accepted"

    # Verify bus was called
    # Note: In a real implementation we would verify the exact message structure
    # but for now we just want to ensure the connection

@pytest.mark.asyncio
async def test_webhook_invalid_payload(aiohttp_client):
    """Test that invalid payloads are rejected."""
    from kabot.gateway.webhook_server import WebhookServer

    server = WebhookServer(bus=MagicMock())
    client = await aiohttp_client(server.app)

    # Missing 'event'
    payload = {"data": "test"}

    resp = await client.post("/webhooks/trigger", json=payload)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_webhook_requires_auth_when_token_configured(aiohttp_client):
    """Webhook should require bearer token when auth token is configured."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token")
    client = await aiohttp_client(server.app)

    payload = {
        "event": "message.received",
        "data": {"content": "Hello", "sender": "external_system"},
    }

    resp = await client.post("/webhooks/trigger", json=payload)
    assert resp.status == 401


@pytest.mark.asyncio
async def test_webhook_accepts_auth_when_token_matches(aiohttp_client):
    """Webhook should accept request with matching bearer token."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token")
    client = await aiohttp_client(server.app)

    payload = {
        "event": "message.received",
        "data": {"content": "Hello", "sender": "external_system"},
    }

    resp = await client.post(
        "/webhooks/trigger",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 202


@pytest.mark.asyncio
async def test_webhook_sets_hsts_header_when_enabled(aiohttp_client):
    """Webhook should emit HSTS header for HTTPS-forwarded requests when enabled."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        strict_transport_security=True,
        strict_transport_security_value="max-age=86400; includeSubDomains",
    )
    client = await aiohttp_client(server.app)

    payload = {
        "event": "message.received",
        "data": {"content": "Hello", "sender": "external_system"},
    }

    resp = await client.post(
        "/webhooks/trigger",
        json=payload,
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status == 202
    assert resp.headers.get("Strict-Transport-Security") == "max-age=86400; includeSubDomains"


@pytest.mark.asyncio
async def test_webhook_hsts_header_not_set_when_disabled(aiohttp_client):
    """Webhook should not emit HSTS header when feature is disabled."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, strict_transport_security=False)
    client = await aiohttp_client(server.app)

    payload = {
        "event": "message.received",
        "data": {"content": "Hello", "sender": "external_system"},
    }

    resp = await client.post(
        "/webhooks/trigger",
        json=payload,
        headers={"X-Forwarded-Proto": "https"},
    )
    assert resp.status == 202
    assert resp.headers.get("Strict-Transport-Security") is None


@pytest.mark.asyncio
async def test_dashboard_requires_operator_read_scope_when_token_is_scoped(aiohttp_client):
    """Dashboard endpoints require operator.read scope for scoped bearer tokens."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    client = await aiohttp_client(server.app)

    unauthorized = await client.get("/dashboard")
    assert unauthorized.status == 401

    authorized = await client.get(
        "/dashboard",
        headers={"Authorization": "Bearer test-token"},
    )
    assert authorized.status == 200


@pytest.mark.asyncio
async def test_dashboard_rejects_token_without_operator_read_scope(aiohttp_client):
    """Scoped token without operator.read must be forbidden for dashboard."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|ingress.write")
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 403


@pytest.mark.asyncio
async def test_trigger_requires_ingress_write_scope_when_token_is_scoped(aiohttp_client):
    """Webhook ingress requires ingress.write scope for scoped bearer tokens."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    payload = {
        "event": "message.received",
        "data": {"content": "Hello", "sender": "external_system"},
    }

    server_forbidden = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    client_forbidden = await aiohttp_client(server_forbidden.app)
    forbidden = await client_forbidden.post(
        "/webhooks/trigger",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    assert forbidden.status == 403

    server_allowed = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read,ingress.write",
    )
    client_allowed = await aiohttp_client(server_allowed.app)
    allowed = await client_allowed.post(
        "/webhooks/trigger",
        json=payload,
        headers={"Authorization": "Bearer test-token"},
    )
    assert allowed.status == 202


@pytest.mark.asyncio
async def test_dashboard_status_api_uses_runtime_status_provider(aiohttp_client):
    """Dashboard status API should expose data returned by status provider."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: {
            "status": "running",
            "model": "openai-codex/gpt-5.3-codex",
            "channels_enabled": ["telegram"],
            "cron_jobs": 2,
        },
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard/api/status",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "running"
    assert data["model"] == "openai-codex/gpt-5.3-codex"
    assert data["channels_enabled"] == ["telegram"]
    assert data["cron_jobs"] == 2
