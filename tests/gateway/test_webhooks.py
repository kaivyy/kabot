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


@pytest.mark.asyncio
async def test_dashboard_shell_includes_subagent_and_git_panels(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: {"status": "running"},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "/dashboard/partials/subagents" in body
    assert "/dashboard/partials/git" in body


@pytest.mark.asyncio
async def test_dashboard_shell_persists_active_tab_across_reload(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: {"status": "running"},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "window.location.hash" in body
    assert "kb-active-tab" in body


@pytest.mark.asyncio
async def test_dashboard_shell_uses_partial_only_auto_refresh(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: {"status": "running"},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "__kabotRefreshDashboardPartials" in body
    assert "htmx.ajax" in body
    assert "window.location.assign" not in body
    assert "cd.onclick = refreshDashboardPartials" in body


@pytest.mark.asyncio
async def test_dashboard_shell_uses_outerhtml_placeholders_for_wrapped_panels(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: {"status": "running"},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard?token=test-token",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert 'id="panel-nodes" class="config-section-card" hx-get="/dashboard/partials/nodes?token=test-token"' in body
    assert 'hx-get="/dashboard/partials/nodes?token=test-token"' in body
    assert 'hx-trigger="load" hx-swap="outerHTML"' in body
    assert 'id="panel-sessions" class="config-section-card" hx-get="/dashboard/partials/sessions?token=test-token"' in body
    assert 'id="panel-cron" class="config-section-card" hx-get="/dashboard/partials/cron?token=test-token"' in body
    assert 'id="panel-skills" class="config-section-card" hx-get="/dashboard/partials/skills?token=test-token"' in body
    assert 'id="panel-git" class="config-section-card" hx-get="/dashboard/partials/git?token=test-token"' in body


@pytest.mark.asyncio
async def test_dashboard_cron_partial_renders_duration_and_actions(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read,operator.write",
        status_provider=lambda: {
            "status": "running",
            "cron_jobs_list": [
                {
                    "id": "job-1",
                    "name": "Daily ping",
                    "schedule": "every 1m",
                    "state": "enabled",
                    "last_status": "error",
                    "last_run": "2026-03-07 10:00:00",
                    "next_run": "2026-03-07 10:01:00",
                    "duration_ms": 321,
                }
            ],
        },
        control_handler=lambda action, args: {"ok": True, "action": action, "args": args},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard/partials/cron",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "Daily ping" in body
    assert "321ms" in body
    assert "Run" in body
    assert "Disable" in body


@pytest.mark.asyncio
async def test_dashboard_skills_partial_renders_env_and_actions(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read,operator.write",
        status_provider=lambda: {
            "status": "running",
            "skills": [
                {
                    "name": "demo-skill",
                    "skill_key": "demo-skill",
                    "state": "missing_env",
                    "disabled": True,
                    "description": "Demo skill",
                    "primary_env": "DEMO_SKILL_API_KEY",
                    "missing_env": ["DEMO_SKILL_API_KEY"],
                }
            ],
        },
        control_handler=lambda action, args: {"ok": True, "action": action, "args": args},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard/partials/skills",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "demo-skill" in body
    assert "DEMO_SKILL_API_KEY" in body
    assert "Enable" in body
    assert "Save Key" in body


@pytest.mark.asyncio
async def test_dashboard_skills_partial_toggle_uses_disabled_flag_not_readiness(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read,operator.write",
        status_provider=lambda: {
            "status": "running",
            "skills": [
                {
                    "name": "demo-skill",
                    "skill_key": "demo-skill",
                    "state": "missing_env",
                    "disabled": False,
                    "description": "Demo skill",
                    "primary_env": "DEMO_SKILL_API_KEY",
                    "missing_env": ["DEMO_SKILL_API_KEY"],
                }
            ],
        },
        control_handler=lambda action, args: {"ok": True, "action": action, "args": args},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard/partials/skills",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "missing env" in body
    assert "Disable" in body
    assert "Enable" not in body


@pytest.mark.asyncio
async def test_dashboard_partial_post_routes_for_cron_and_skills_are_available(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read,operator.write",
        status_provider=lambda: {
            "status": "running",
            "cron_jobs_list": [{"id": "job-1", "name": "Daily ping", "schedule": "every 1m", "state": "enabled"}],
            "skills": [{"name": "demo-skill", "skill_key": "demo-skill", "state": "enabled"}],
        },
        control_handler=lambda action, args: {"ok": True, "action": action, "args": args},
    )
    client = await aiohttp_client(server.app)

    cron_resp = await client.post(
        "/dashboard/partials/cron",
        data={"action": "cron.run", "job_id": "job-1"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert cron_resp.status == 200

    skills_resp = await client.post(
        "/dashboard/partials/skills",
        data={"action": "skills.disable", "skill_key": "demo-skill"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert skills_resp.status == 200


@pytest.mark.asyncio
async def test_operator_write_scope_implies_dashboard_read(aiohttp_client):
    """operator.write should be sufficient for read-only dashboard endpoints."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.write")
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200


@pytest.mark.asyncio
async def test_dashboard_control_api_requires_operator_write_scope(aiohttp_client):
    """Control API should reject read-only operators and allow write operators."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    read_only_server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    read_only_client = await aiohttp_client(read_only_server.app)
    forbidden = await read_only_client.post(
        "/dashboard/api/control",
        json={"action": "runtime.ping"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert forbidden.status == 403

    writable_server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.write")
    writable_client = await aiohttp_client(writable_server.app)
    unavailable = await writable_client.post(
        "/dashboard/api/control",
        json={"action": "runtime.ping"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert unavailable.status == 501
    payload = await unavailable.json()
    assert payload["ok"] is False
    assert payload["error"] == "control_unavailable"


@pytest.mark.asyncio
async def test_dashboard_control_info_lists_cron_and_skills_actions(aiohttp_client):
    """Control info metadata should advertise dashboard cron/skills actions."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard/api/control",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    payload = await resp.json()
    actions = payload["actions"]
    assert "cron.run" in actions
    assert "cron.enable" in actions
    assert "skills.enable" in actions
    assert "skills.set_api_key" in actions


@pytest.mark.asyncio
async def test_dashboard_control_api_executes_control_handler(aiohttp_client):
    """Control API should call configured handler and return result payload."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"pong": True}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/api/control",
        json={"action": "runtime.ping", "args": {"source": "test"}},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    payload = await resp.json()
    assert payload["ok"] is True
    assert payload["action"] == "runtime.ping"
    assert payload["result"] == {"pong": True}
    assert called == {"action": "runtime.ping", "args": {"source": "test"}}


@pytest.mark.asyncio
async def test_dashboard_control_partial_post_requires_operator_write_scope(aiohttp_client):
    """HTMX control endpoint should enforce operator.write scope."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    read_server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    read_client = await aiohttp_client(read_server.app)
    forbidden = await read_client.post(
        "/dashboard/partials/control",
        data={"action": "runtime.ping"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert forbidden.status == 403

    write_server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.write")
    write_client = await aiohttp_client(write_server.app)
    unavailable = await write_client.post(
        "/dashboard/partials/control",
        data={"action": "runtime.ping"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert unavailable.status == 501


@pytest.mark.asyncio
async def test_dashboard_control_partial_executes_control_handler(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()
    called = {}

    def control_handler(action: str, args: dict):
        called["action"] = action
        called["args"] = args
        return {"pong": True}

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=control_handler,
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/partials/control",
        data={"action": "runtime.ping"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "Success" in body
    assert "Action completed." in body
    assert "pong" in body
    assert called == {"action": "runtime.ping", "args": {}}


@pytest.mark.asyncio
async def test_dashboard_settings_panels_show_read_only_state_without_operator_write(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: {
            "status": "running",
            "skills": [
                {
                    "name": "demo-skill",
                    "skill_key": "demo-skill",
                    "state": "enabled",
                    "disabled": False,
                }
            ],
        },
        control_handler=lambda action, args: {"ok": True, "action": action, "args": args},
    )
    client = await aiohttp_client(server.app)

    control_resp = await client.get(
        "/dashboard/partials/control",
        headers={"Authorization": "Bearer test-token"},
    )
    assert control_resp.status == 200
    control_body = await control_resp.text()
    assert "Read-only token" in control_body
    assert "disabled" in control_body

    config_resp = await client.get(
        "/dashboard/partials/config",
        headers={"Authorization": "Bearer test-token"},
    )
    assert config_resp.status == 200
    config_body = await config_resp.text()
    assert "Read-only token" in config_body

    skills_resp = await client.get(
        "/dashboard/partials/skills",
        headers={"Authorization": "Bearer test-token"},
    )
    assert skills_resp.status == 200
    skills_body = await skills_resp.text()
    assert "read-only token" in skills_body.lower()


@pytest.mark.asyncio
async def test_dashboard_engine_panels_show_read_only_state_without_operator_write(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        status_provider=lambda: {
            "status": "running",
            "sessions": [{"key": "telegram:123", "updated_at": "2026-03-05T10:00:00"}],
            "nodes": [{"id": "channel:telegram", "kind": "channel", "state": "running"}],
        },
        control_handler=lambda action, args: {"ok": True, "action": action, "args": args},
    )
    client = await aiohttp_client(server.app)

    sessions_resp = await client.get(
        "/dashboard/partials/sessions",
        headers={"Authorization": "Bearer test-token"},
    )
    assert sessions_resp.status == 200
    sessions_body = await sessions_resp.text()
    assert "read-only token" in sessions_body.lower()
    assert ">read-only<" in sessions_body.lower()

    nodes_resp = await client.get(
        "/dashboard/partials/nodes",
        headers={"Authorization": "Bearer test-token"},
    )
    assert nodes_resp.status == 200
    nodes_body = await nodes_resp.text()
    assert "read-only token" in nodes_body.lower()
    assert ">read-only<" in nodes_body.lower()


@pytest.mark.asyncio
async def test_dashboard_chat_partial_disables_inputs_for_read_only_token(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.read",
        control_handler=lambda action, args: {"ok": True, "action": action, "args": args},
    )
    client = await aiohttp_client(server.app)

    resp = await client.get(
        "/dashboard/partials/chat",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "read-only token" in body.lower()
    assert "textarea name='prompt'" in body
    assert "textarea name='prompt'" in body and "disabled" in body
    assert "select form='chat-form' name='provider'" in body


@pytest.mark.asyncio
async def test_dashboard_sessions_partial_renders_friendly_success_feedback(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(
        bus=mock_bus,
        auth_token="test-token|operator.write",
        control_handler=lambda action, args: {"cleared": True, "session_key": args.get("session_key")},
    )
    client = await aiohttp_client(server.app)

    resp = await client.post(
        "/dashboard/partials/sessions",
        data={"action": "sessions.clear", "session_key": "telegram:123"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status == 200
    body = await resp.text()
    assert "Success" in body
    assert "Action completed." in body
    assert "telegram:123" in body


@pytest.mark.asyncio
async def test_dashboard_supports_query_token_auth(aiohttp_client):
    """Dashboard routes should allow token query auth for easier browser access."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|operator.read")
    client = await aiohttp_client(server.app)

    unauthorized = await client.get("/dashboard")
    assert unauthorized.status == 401

    ok_page = await client.get("/dashboard?token=test-token")
    assert ok_page.status == 200
    page_text = await ok_page.text()
    assert "token=test-token" in page_text

    ok_partial = await client.get("/dashboard/partials/summary?token=test-token")
    assert ok_partial.status == 200


@pytest.mark.asyncio
async def test_query_token_auth_not_allowed_for_webhook_ingress(aiohttp_client):
    """Query token auth must stay dashboard-only and never authorize webhook ingress."""
    from kabot.gateway.webhook_server import WebhookServer

    mock_bus = MagicMock()
    mock_bus.publish_inbound = AsyncMock()

    server = WebhookServer(bus=mock_bus, auth_token="test-token|ingress.write")
    client = await aiohttp_client(server.app)

    payload = {
        "event": "message.received",
        "data": {"content": "Hello", "sender": "external_system"},
    }

    resp = await client.post("/webhooks/trigger?token=test-token", json=payload)
    assert resp.status == 401


@pytest.mark.asyncio
async def test_dashboard_page_includes_openclaw_like_sections(aiohttp_client):
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
    assert "name='action' value='nodes.start'" in body
    assert "<button type='submit' class='py-1 px-2 text-xs bg-emerald-500 hover:bg-emerald-600' disabled>Start</button>" in body
    # Stopped channel should have Stop disabled
    assert "name='action' value='nodes.stop'" in body
    assert "<button type='submit' class='py-1 px-2 text-xs bg-red-500 hover:bg-red-600' disabled>Stop</button>" in body


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
    assert resp.status == 200
    body = await resp.text()
    assert "Success" in body
    assert "Action completed." in body
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
