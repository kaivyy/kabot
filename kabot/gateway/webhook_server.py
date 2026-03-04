"""Webhook ingress server and lightweight dashboard surface."""

from __future__ import annotations

import html
import time
from typing import Any, Callable

from aiohttp import web

from kabot.bus.events import InboundMessage
from kabot.bus.queue import MessageBus
from kabot.integrations.meta_webhook import parse_meta_inbound, verify_meta_signature


class WebhookServer:
    def __init__(
        self,
        bus: MessageBus,
        auth_token: str | None = None,
        meta_verify_token: str | None = None,
        meta_app_secret: str | None = None,
        strict_transport_security: bool = False,
        strict_transport_security_value: str = "max-age=31536000; includeSubDomains",
        status_provider: Callable[[], dict[str, Any]] | None = None,
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
        self.app.router.add_get("/dashboard/api/status", self.handle_dashboard_status_api)
        self.app.router.add_post("/webhooks/trigger", self.handle_trigger)
        self.app.router.add_get("/webhooks/meta", self.handle_meta_verify)
        self.app.router.add_post("/webhooks/meta", self.handle_meta_event)

    @staticmethod
    def _parse_auth_token(auth_token: str | None) -> tuple[str, set[str]]:
        raw = str(auth_token or "").strip()
        if not raw:
            return "", set()
        if "|" not in raw:
            return raw, set()
        token, raw_scopes = raw.split("|", 1)
        scopes = {
            item.strip().lower()
            for item in str(raw_scopes or "").split(",")
            if item and item.strip()
        }
        return token.strip(), scopes

    def _extract_bearer(self, request: web.Request) -> str:
        auth_header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not auth_header.startswith(prefix):
            return ""
        return auth_header[len(prefix):].strip()

    def _has_scope(self, required_scope: str) -> bool:
        if not required_scope:
            return True
        if not self.auth_scopes:
            # Backward compatibility: plain bearer token grants full access.
            return True
        normalized = str(required_scope).strip().lower()
        return (
            normalized in self.auth_scopes
            or "*" in self.auth_scopes
            or "admin" in self.auth_scopes
            or "operator.admin" in self.auth_scopes
        )

    def _authorize(self, request: web.Request, required_scope: str = "") -> web.Response | None:
        if not self.auth_token:
            return None
        bearer = self._extract_bearer(request)
        if bearer != self.auth_token:
            return web.Response(text="Unauthorized", status=401)
        if required_scope and not self._has_scope(required_scope):
            return web.Response(text="Forbidden", status=403)
        return None

    def _is_https_request(self, request: web.Request) -> bool:
        if bool(getattr(request, "secure", False)):
            return True

        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if forwarded_proto:
            tokens = [token.strip().lower() for token in forwarded_proto.split(",")]
            if "https" in tokens:
                return True

        forwarded = request.headers.get("Forwarded", "").lower()
        if "proto=https" in forwarded:
            return True

        return False

    def _read_dashboard_status(self) -> dict[str, Any]:
        payload: dict[str, Any]
        if callable(self.status_provider):
            try:
                payload = self.status_provider() or {}
            except Exception as exc:
                payload = {"status": "error", "error": f"status_provider_failed: {exc}"}
        else:
            payload = {"status": "running"}
        payload.setdefault("status", "running")
        payload.setdefault("uptime_seconds", max(0, int(time.time() - self.started_at)))
        return payload

    async def handle_root(self, _request: web.Request) -> web.Response:
        raise web.HTTPFound("/dashboard")

    async def handle_dashboard(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize(request, required_scope="operator.read")
        if unauthorized is not None:
            return unauthorized

        body = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Kabot Dashboard</title>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; background: #f6f7f9; color: #111827; }
    main { max-width: 960px; margin: 0 auto; padding: 18px; }
    .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; margin-bottom: 14px; }
    .muted { color: #6b7280; font-size: 0.92rem; }
    h1 { font-size: 1.2rem; margin: 0 0 8px; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.9rem; }
    table { width: 100%; border-collapse: collapse; }
    td, th { border-bottom: 1px solid #f0f1f3; padding: 8px 6px; text-align: left; vertical-align: top; }
  </style>
</head>
<body>
  <main>
    <div class="card">
      <h1>Kabot Dashboard</h1>
      <div class="muted">Lightweight SSR + HTMX monitor. Refreshes every 5 seconds.</div>
    </div>
    <div
      class="card"
      hx-get="/dashboard/partials/summary"
      hx-trigger="load, every 5s"
      hx-swap="innerHTML"
    >Loading summary...</div>
    <div
      class="card"
      hx-get="/dashboard/partials/runtime"
      hx-trigger="load, every 5s"
      hx-swap="innerHTML"
    >Loading runtime...</div>
  </main>
</body>
</html>"""
        return web.Response(text=body, content_type="text/html")

    async def handle_dashboard_summary(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize(request, required_scope="operator.read")
        if unauthorized is not None:
            return unauthorized

        status = self._read_dashboard_status()
        status_text = html.escape(str(status.get("status", "unknown")))
        uptime = int(status.get("uptime_seconds", 0) or 0)
        channels = status.get("channels_enabled", [])
        if not isinstance(channels, list):
            channels = []
        channels_text = ", ".join(str(item) for item in channels if str(item).strip()) or "-"
        channels_text = html.escape(channels_text)
        cron_jobs = int(status.get("cron_jobs", 0) or 0)
        model = html.escape(str(status.get("model", "-")))

        fragment = (
            "<h2>Summary</h2>"
            "<table>"
            f"<tr><th>Status</th><td class='mono'>{status_text}</td></tr>"
            f"<tr><th>Uptime</th><td class='mono'>{uptime}s</td></tr>"
            f"<tr><th>Model</th><td class='mono'>{model}</td></tr>"
            f"<tr><th>Channels</th><td>{channels_text}</td></tr>"
            f"<tr><th>Cron jobs</th><td class='mono'>{cron_jobs}</td></tr>"
            "</table>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_runtime(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize(request, required_scope="operator.read")
        if unauthorized is not None:
            return unauthorized

        status = self._read_dashboard_status()
        extra = {
            key: value
            for key, value in status.items()
            if key not in {"status", "uptime_seconds", "channels_enabled", "cron_jobs", "model"}
        }
        pretty = html.escape(str(extra or {}))
        fragment = (
            "<h2>Runtime Details</h2>"
            "<div class='muted'>Structured payload from runtime status provider.</div>"
            f"<pre class='mono'>{pretty}</pre>"
        )
        return web.Response(text=fragment, content_type="text/html")

    async def handle_dashboard_status_api(self, request: web.Request) -> web.Response:
        unauthorized = self._authorize(request, required_scope="operator.read")
        if unauthorized is not None:
            return unauthorized
        return web.json_response(self._read_dashboard_status())

    async def handle_trigger(self, request: web.Request) -> web.Response:
        """Handle incoming webhook trigger."""
        unauthorized = self._authorize(request, required_scope="ingress.write")
        if unauthorized is not None:
            return unauthorized

        try:
            payload = await request.json()
        except Exception:
            return web.Response(text="Invalid JSON", status=400)

        event_type = payload.get("event")
        if not event_type:
            return web.Response(text="Missing event type", status=400)

        data = payload.get("data", {})

        # Convert webhook payload to InboundMessage
        # This allows the agent to process it like any other message
        if event_type == "message.received":
            content = data.get("content", "")
            sender = data.get("sender", "webhook")

            message = InboundMessage(
                channel="webhook",
                sender_id=sender,
                chat_id="direct",  # Webhooks usually target the bot directly
                content=content,
                # Add extra context if needed
            )

            await self.bus.publish_inbound(message)
            return web.Response(text="Accepted", status=202)

        return web.Response(text=f"Unknown event type: {event_type}", status=400)

    async def handle_meta_verify(self, request: web.Request) -> web.Response:
        """Handle Meta webhook verification challenge."""
        if not self.meta_verify_token:
            return web.Response(text="Meta webhook disabled", status=404)

        mode = request.query.get("hub.mode", "")
        verify_token = request.query.get("hub.verify_token", "")
        challenge = request.query.get("hub.challenge", "")

        if mode == "subscribe" and verify_token == self.meta_verify_token:
            return web.Response(text=challenge, status=200)

        return web.Response(text="Forbidden", status=403)

    async def handle_meta_event(self, request: web.Request) -> web.Response:
        """Handle Meta webhook event ingress."""
        unauthorized = self._authorize(request, required_scope="ingress.write")
        if unauthorized is not None:
            return unauthorized

        raw_body = await request.read()

        if self.meta_app_secret:
            signature = request.headers.get("X-Hub-Signature-256", "")
            if not verify_meta_signature(raw_body, self.meta_app_secret, signature):
                return web.Response(text="Unauthorized", status=401)

        try:
            payload = await request.json()
        except Exception:
            return web.Response(text="Invalid JSON", status=400)

        inbound_messages = parse_meta_inbound(payload)
        for msg in inbound_messages:
            await self.bus.publish_inbound(msg)

        return web.Response(text="Accepted", status=202)

    async def start(self, host: str = "0.0.0.0", port: int = 18790):
        """Start the webhook server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        return runner
