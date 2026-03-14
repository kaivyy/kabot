"""Tests for Webhook Ingress Infrastructure.

Split from tests/gateway/test_webhooks.py to keep test modules below 1000 lines.
Chunk 2: test_dashboard_page_includes_reference_sections .. test_dashboard_chat_stream_api_returns_sse_snapshot.
"""
import re
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_dashboard_page_includes_reference_sections(aiohttp_client):
    """Dashboard HTML should expose chat/sessions/nodes/config panels."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    client = await aiohttp_client(server.app)

    resp = await client.get("/dashboard?token=test-token")
    assert resp.status == 200
    body = await resp.text()
    assert "id=\"panel-sessions\"" in body
    assert "id=\"panel-nodes\"" in body
    assert "/dashboard/partials/chat?token=test-token" in body
    assert "/dashboard/partials/sessions?token=test-token" in body
    assert "/dashboard/partials/nodes?token=test-token" in body
    assert "/dashboard/partials/config?token=test-token" in body

@pytest.mark.asyncio
async def test_dashboard_new_status_apis_return_provider_data(aiohttp_client):
    """Sessions/nodes/config APIs should reflect status provider payload."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    status_payload = {
        "status": "running",
        "sessions": [{"key": "telegram:123", "updated_at": "2026-03-05T10:00:00"}],
        "nodes": [{"id": "gateway", "kind": "runtime", "state": "running"}],
        "config": {"runtime": {"performance": {"token_mode": "boros"}}},
    }

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: status_payload,
    )
    client = await aiohttp_client(server.app)

    sessions_resp = await client.get("/dashboard/api/sessions", headers={"Authorization": "Bearer test-token"})
    assert sessions_resp.status == 200
    sessions_data = await sessions_resp.json()
    assert sessions_data["sessions"] == status_payload["sessions"]

    nodes_resp = await client.get("/dashboard/api/nodes", headers={"Authorization": "Bearer test-token"})
    assert nodes_resp.status == 200
    nodes_data = await nodes_resp.json()
    assert nodes_data["nodes"] == status_payload["nodes"]

    config_resp = await client.get("/dashboard/api/config", headers={"Authorization": "Bearer test-token"})
    assert config_resp.status == 200
    config_data = await config_resp.json()
    assert config_data["config"] == status_payload["config"]

@pytest.mark.asyncio
async def test_dashboard_sessions_partial_requires_operator_write_scope(aiohttp_client):
    """Dashboard sessions action endpoint should enforce operator.write."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    read_server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    read_client = await aiohttp_client(read_server.app)
    forbidden = await read_client.post(
        "/dashboard/partials/sessions",
        data={"action": "sessions.clear", "session_key": "telegram:123"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert forbidden.status == 403

@pytest.mark.asyncio
async def test_dashboard_sessions_partial_executes_control_handler(aiohttp_client):
    """Dashboard sessions partial should execute control handler with session args."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"cleared": True, "session_key": args.get("session_key")}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/partials/sessions",
        data={"action": "sessions.clear", "session_key": "telegram:123"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "<h2>Sessions</h2>" in body
    assert "telegram:123" in body
    assert called["action"] == "sessions.clear"
    assert called["args"]["session_key"] == "telegram:123"

@pytest.mark.asyncio
async def test_dashboard_sessions_api_write_executes_control_handler(aiohttp_client):
    """Dashboard sessions write API should execute control handler actions."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"deleted": True, "session_key": args.get("session_key")}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/api/sessions",
        json={"action": "sessions.delete", "session_key": "telegram:123"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["ok"] is True
    assert called["action"] == "sessions.delete"
    assert called["args"]["session_key"] == "telegram:123"

@pytest.mark.asyncio
async def test_dashboard_nodes_partial_requires_operator_write_scope(aiohttp_client):
    """Dashboard nodes action endpoint should enforce operator.write."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    read_server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    read_client = await aiohttp_client(read_server.app)
    forbidden = await read_client.post(
        "/dashboard/partials/nodes",
        data={"action": "nodes.restart", "node_id": "channel:telegram"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert forbidden.status == 403

@pytest.mark.asyncio
async def test_dashboard_nodes_partial_executes_control_handler(aiohttp_client):
    """Dashboard nodes partial should execute control handler with node args."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"restarted": True, "node_id": args.get("node_id")}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/partials/nodes",
        data={"action": "nodes.restart", "node_id": "channel:telegram"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "<h2>Nodes</h2>" in body
    assert "channel:telegram" in body
    assert called["action"] == "nodes.restart"
    assert called["args"]["node_id"] == "channel:telegram"

@pytest.mark.asyncio
async def test_dashboard_nodes_and_sessions_partials_target_panel_for_live_refresh(aiohttp_client):
    """Nodes/Sessions forms should target full panel containers for immediate refresh."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    status_payload = {
        "status": "running",
        "sessions": [{"key": "telegram:123", "updated_at": "2026-03-05T10:00:00"}],
        "nodes": [{"id": "channel:telegram", "kind": "channel", "state": "running"}],
    }

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        status_provider=lambda: status_payload,
        control_handler=lambda _action, _args: {"ok": True},
    )
    client = await aiohttp_client(server.app)

    sessions_resp = await client.get("/dashboard/partials/sessions?token=test-token")
    assert sessions_resp.status == 200
    sessions_body = await sessions_resp.text()
    assert "hx-target='#panel-sessions'" in sessions_body

    nodes_resp = await client.get("/dashboard/partials/nodes?token=test-token")
    assert nodes_resp.status == 200
    nodes_body = await nodes_resp.text()
    assert "hx-target='#panel-nodes'" in nodes_body

@pytest.mark.asyncio
async def test_dashboard_nodes_api_write_executes_control_handler(aiohttp_client):
    """Dashboard nodes write API should execute control handler actions."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"restarted": True, "node_id": args.get("node_id")}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/api/nodes",
        json={"action": "nodes.restart", "node_id": "channel:telegram"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["ok"] is True
    assert called["action"] == "nodes.restart"
    assert called["args"]["node_id"] == "channel:telegram"

@pytest.mark.asyncio
async def test_dashboard_nodes_partial_disables_state_incompatible_actions(aiohttp_client):
    """Nodes panel should disable buttons that contradict current node state."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    status_payload = {
        "status": "running",
        "nodes": [
            {"id": "channel:telegram", "kind": "channel", "state": "running"},
            {"id": "channel:discord", "kind": "channel", "state": "stopped"},
            {"id": "gateway", "kind": "runtime", "state": "running"},
        ],
    }

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        status_provider=lambda: status_payload,
        control_handler=lambda _action, _args: {"ok": True},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get("/dashboard/partials/nodes?token=test-token")
    assert resp.status == 200
    body = await resp.text()
    assert "channel:telegram" in body
    assert "channel:discord" in body
    assert "gateway" in body
    # Running channel should have Start disabled
    assert re.search(
        r"name='action' value='nodes\.start'.+?<button type='submit'[^>]*disabled>Start</button>",
        body,
        re.DOTALL,
    )
    # Stopped channel should have Stop disabled
    assert re.search(
        r"name='action' value='nodes\.stop'.+?<button type='submit'[^>]*disabled>Stop</button>",
        body,
        re.DOTALL,
    )

@pytest.mark.asyncio
async def test_dashboard_chat_partial_requires_operator_write_scope(aiohttp_client):
    """Dashboard chat send endpoint should enforce operator.write."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    read_server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    read_client = await aiohttp_client(read_server.app)
    forbidden = await read_client.post(
        "/dashboard/partials/chat",
        data={"prompt": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert forbidden.status == 403

@pytest.mark.asyncio
async def test_dashboard_chat_partial_executes_control_handler(aiohttp_client):
    """Dashboard chat partial should call control handler via chat.send action."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"content": "hello from runtime"}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/partials/chat",
        data={
            "prompt": "ping",
            "session_key": "dashboard:chat",
            "provider": "openrouter",
            "model": "auto",
            "fallbacks": "groq/llama3-70b-8192,openai/gpt-4o-mini",
        },
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 202
    body = await resp.text()
    assert "Queued: sending to runtime" in body
    assert called["action"] == "chat.send"
    assert called["args"]["prompt"] == "ping"
    assert called["args"]["session_key"] == "dashboard:chat"
    assert called["args"]["provider"] == "openrouter"
    assert called["args"]["model"] == "auto"
    assert called["args"]["fallbacks"] == "groq/llama3-70b-8192,openai/gpt-4o-mini"

@pytest.mark.asyncio
async def test_dashboard_config_partial_renders_friendly_success_feedback(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"message": f"Token mode set to {args.get('token_mode')}"}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/partials/config",
        data={"action": "config.set_token_mode", "token_mode": "hemat"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "Success" in body
    assert "Token mode set to hemat" in body
    assert called == {"action": "config.set_token_mode", "args": {"token_mode": "hemat"}}

@pytest.mark.asyncio
async def test_dashboard_chat_partial_includes_live_log_stream_endpoint(aiohttp_client):
    """Chat partial should include live-log stream endpoint for current session."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    client = await aiohttp_client(server.app)

    resp = await client.get("/dashboard/partials/chat?token=test-token")
    assert resp.status == 200
    body = await resp.text()
    assert "/dashboard/partials/chat/log?" in body
    assert "/dashboard/api/chat/stream?" in body
    assert "session_key=dashboard%3Aweb" in body
    assert "token=test-token" in body
    assert "name='provider'" in body
    assert "name='model'" in body
    assert "name='fallbacks'" in body
    assert "id='model-suggestions'" in body
    assert "data-model-map=" in body
    assert "id='fallback-builder'" in body
    assert "id='fallback-input'" in body
    assert "id='fallback-items'" in body
    assert "id='fallback-add-btn'" in body
    assert "kabotScrollChatToLatest" in body
    assert "htmx:afterSwap" in body

@pytest.mark.asyncio
async def test_dashboard_chat_history_api_and_partial_use_history_provider(aiohttp_client):
    """Chat history API/partial should render chat_history_provider payload."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    history_items = [
        {"role": "user", "content": "hello", "timestamp": "2026-03-05T10:00:00"},
        {"role": "assistant", "content": "hi there", "timestamp": "2026-03-05T10:00:01"},
    ]

    def _history_provider(session_key: str, limit: int):
        assert session_key == "dashboard:web"
        assert limit == 30
        return history_items

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        chat_history_provider=_history_provider,
    )
    client = await aiohttp_client(server.app)

    api_resp = await client.get(
        "/dashboard/api/chat/history?session_key=dashboard:web",
        headers={"Authorization": "Bearer test-token"},
    )
    assert api_resp.status == 200
    api_data = await api_resp.json()
    assert api_data["session_key"] == "dashboard:web"
    assert api_data["messages"] == [
        {**item, "metadata": {}}
        for item in history_items
    ]

    partial_resp = await client.get(
        "/dashboard/partials/chat/log?session_key=dashboard:web",
        headers={"Authorization": "Bearer test-token"},
    )
    assert partial_resp.status == 200
    partial_body = await partial_resp.text()
    assert "hello" in partial_body
    assert "hi there" in partial_body

@pytest.mark.asyncio
async def test_dashboard_chat_partial_renders_status_phase_badge(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    history_items = [
        {
            "role": "assistant",
            "content": "Plan approved.",
            "timestamp": "2026-03-07T10:00:01",
            "metadata": {"type": "status_update", "phase": "approved"},
        },
    ]

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        chat_history_provider=lambda _session_key, _limit: history_items,
    )
    client = await aiohttp_client(server.app)

    partial_resp = await client.get(
        "/dashboard/partials/chat/log?session_key=dashboard:web",
        headers={"Authorization": "Bearer test-token"},
    )
    assert partial_resp.status == 200
    partial_body = await partial_resp.text()
    assert "Plan approved." in partial_body
    assert "approved" in partial_body
    assert "kb-phase-badge" in partial_body

@pytest.mark.asyncio
async def test_dashboard_chat_stream_api_returns_sse_snapshot(aiohttp_client):
    """Chat stream endpoint should emit SSE snapshot from history provider."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    history_items = [
        {"role": "user", "content": "hello", "timestamp": "2026-03-05T10:00:00"},
        {"role": "assistant", "content": "hi there", "timestamp": "2026-03-05T10:00:01"},
    ]

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        chat_history_provider=lambda _session_key, _limit: history_items,
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard/api/chat/stream?session_key=dashboard:web&once=1",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    assert "text/event-stream" in (resp.headers.get("Content-Type") or "")
    body = await resp.text()
    assert "event: snapshot" in body
    assert "hello" in body
    assert "hi there" in body
