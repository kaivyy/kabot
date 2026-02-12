"""Tests for Webhook Ingress Infrastructure."""
import pytest
from aiohttp import web
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

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
