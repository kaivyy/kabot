"""Webhook ingress server and lightweight dashboard surface."""

from __future__ import annotations

import time
from typing import Any, Callable

from aiohttp import web

from kabot.bus.queue import MessageBus
from kabot.gateway.handlers._base import BaseMixin
from kabot.gateway.handlers.chat import ChatMixin
from kabot.gateway.handlers.config import ConfigMixin
from kabot.gateway.handlers.control import ControlMixin
from kabot.gateway.handlers.dashboard import DashboardMixin
from kabot.gateway.handlers.nodes import NodesMixin
from kabot.gateway.handlers.sessions import SessionsMixin
from kabot.gateway.handlers.webhooks import WebhookMixin


class WebhookServer(
    BaseMixin,
    DashboardMixin,
    ChatMixin,
    SessionsMixin,
    NodesMixin,
    ConfigMixin,
    ControlMixin,
    WebhookMixin,
):
    _ROUTE_SCOPE_RULES: tuple[tuple[str, str, str], ...] = (
        ("GET", "/dashboard", "operator.read"),
        ("GET", "/dashboard/partials/*", "operator.read"),
        ("GET", "/dashboard/api/status", "operator.read"),
        ("GET", "/dashboard/api/chat/history", "operator.read"),
        ("GET", "/dashboard/api/chat/stream", "operator.read"),
        ("GET", "/dashboard/api/sessions", "operator.read"),
        ("GET", "/dashboard/api/nodes", "operator.read"),
        ("GET", "/dashboard/api/config", "operator.read"),
        ("POST", "/dashboard/api/sessions", "operator.write"),
        ("POST", "/dashboard/api/nodes", "operator.write"),
        ("POST", "/dashboard/api/chat", "operator.write"),
        ("POST", "/dashboard/api/config", "operator.write"),
        ("GET", "/dashboard/api/control", "operator.read"),
        ("POST", "/dashboard/partials/sessions", "operator.write"),
        ("POST", "/dashboard/partials/nodes", "operator.write"),
        ("POST", "/dashboard/partials/chat", "operator.write"),
        ("POST", "/dashboard/partials/config", "operator.write"),
        ("POST", "/dashboard/partials/control", "operator.write"),
        ("POST", "/dashboard/partials/cron", "operator.write"),
        ("POST", "/dashboard/partials/skills", "operator.write"),
        ("POST", "/dashboard/api/control", "operator.write"),
        ("POST", "/webhooks/trigger", "ingress.write"),
        ("POST", "/webhooks/meta", "ingress.write"),
    )

    def __init__(
        self,
        bus: MessageBus,
        auth_token: str | None = None,
        meta_verify_token: str | None = None,
        meta_app_secret: str | None = None,
        strict_transport_security: bool = False,
        strict_transport_security_value: str = "max-age=31536000; includeSubDomains",
        status_provider: Callable[[], dict[str, Any]] | None = None,
        chat_history_provider: Callable[[str, int], Any] | None = None,
        control_handler: Callable[[str, dict[str, Any]], Any] | None = None,
    ):
        self.bus = bus
        self.auth_token, self.auth_scopes = self._parse_auth_token(auth_token)
        self.meta_verify_token = (meta_verify_token or "").strip()
        self.meta_app_secret = (meta_app_secret or "").strip()
        self.strict_transport_security = bool(strict_transport_security)
        self.strict_transport_security_value = (
            strict_transport_security_value.strip()
            if isinstance(strict_transport_security_value, str)
            else "max-age=31536000; includeSubDomains"
        ) or "max-age=31536000; includeSubDomains"
        self.started_at = time.time()
        self.status_provider = status_provider
        self.chat_history_provider = chat_history_provider
        self.control_handler = control_handler

        @web.middleware
        async def security_headers_middleware(
            request: web.Request,
            handler,
        ) -> web.StreamResponse:
            response = await handler(request)
            if self.strict_transport_security and self._is_https_request(request):
                response.headers["Strict-Transport-Security"] = self.strict_transport_security_value
            return response

        self.app = web.Application(middlewares=[security_headers_middleware])
        self.app.router.add_get("/", self.handle_root)
        self.app.router.add_get("/dashboard", self.handle_dashboard)
        self.app.router.add_get("/dashboard/partials/summary", self.handle_dashboard_summary)
        self.app.router.add_get("/dashboard/partials/runtime", self.handle_dashboard_runtime)
        self.app.router.add_get("/dashboard/partials/chat", self.handle_dashboard_chat)
        self.app.router.add_get("/dashboard/partials/chat/log", self.handle_dashboard_chat_log)
        self.app.router.add_get("/dashboard/partials/sessions", self.handle_dashboard_sessions)
        self.app.router.add_get("/dashboard/partials/nodes", self.handle_dashboard_nodes)
        self.app.router.add_get("/dashboard/partials/config", self.handle_dashboard_config)
        self.app.router.add_get("/dashboard/partials/control", self.handle_dashboard_control)
        # ── New panels ──────────────────────────────────────────────
        self.app.router.add_get("/dashboard/partials/metrics", self.handle_dashboard_metrics)
        self.app.router.add_get("/dashboard/partials/alerts", self.handle_dashboard_alerts)
        self.app.router.add_get("/dashboard/partials/health", self.handle_dashboard_health)
        self.app.router.add_get("/dashboard/partials/cost", self.handle_dashboard_cost)
        self.app.router.add_get("/dashboard/partials/charts", self.handle_dashboard_charts)
        self.app.router.add_get("/dashboard/partials/channels", self.handle_dashboard_channels)
        self.app.router.add_get("/dashboard/partials/cron", self.handle_dashboard_cron)
        self.app.router.add_get("/dashboard/partials/models", self.handle_dashboard_models)
        self.app.router.add_get("/dashboard/partials/skills", self.handle_dashboard_skills)
        self.app.router.add_get("/dashboard/partials/subagents", self.handle_dashboard_subagents)
        self.app.router.add_get("/dashboard/partials/git", self.handle_dashboard_git)
        # ── API endpoints ───────────────────────────────────────────
        self.app.router.add_get("/dashboard/api/status", self.handle_dashboard_status_api)
        self.app.router.add_get("/dashboard/api/chat/history", self.handle_dashboard_chat_history_api)
        self.app.router.add_get("/dashboard/api/chat/stream", self.handle_dashboard_chat_stream_api)
        self.app.router.add_get("/dashboard/api/sessions", self.handle_dashboard_sessions_api)
        self.app.router.add_get("/dashboard/api/nodes", self.handle_dashboard_nodes_api)
        self.app.router.add_get("/dashboard/api/config", self.handle_dashboard_config_api)
        self.app.router.add_post("/dashboard/api/sessions", self.handle_dashboard_sessions_update_api)
        self.app.router.add_post("/dashboard/api/nodes", self.handle_dashboard_nodes_update_api)
        self.app.router.add_post("/dashboard/api/chat", self.handle_dashboard_chat_api)
        self.app.router.add_post("/dashboard/api/config", self.handle_dashboard_config_update_api)
        self.app.router.add_get("/dashboard/api/control", self.handle_dashboard_control_info)
        self.app.router.add_post("/dashboard/api/control", self.handle_dashboard_control_api)
        self.app.router.add_post("/dashboard/partials/sessions", self.handle_dashboard_sessions_action)
        self.app.router.add_post("/dashboard/partials/nodes", self.handle_dashboard_nodes_action)
        self.app.router.add_post("/dashboard/partials/chat", self.handle_dashboard_chat_action)
        self.app.router.add_post("/dashboard/partials/config", self.handle_dashboard_config_action)
        self.app.router.add_post("/dashboard/partials/control", self.handle_dashboard_control_action)
        self.app.router.add_post("/dashboard/partials/cron", self.handle_dashboard_cron_action)
        self.app.router.add_post("/dashboard/partials/skills", self.handle_dashboard_skills_action)
        self.app.router.add_post("/webhooks/trigger", self.handle_trigger)
        self.app.router.add_get("/webhooks/meta", self.handle_meta_verify)
        self.app.router.add_post("/webhooks/meta", self.handle_meta_event)

    async def start(self, host: str = "0.0.0.0", port: int = 18790):
        """Start the webhook server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        return runner
