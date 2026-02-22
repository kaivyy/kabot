"""Webhook Ingress Server."""
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
    ):
        self.bus = bus
        self.auth_token = (auth_token or "").strip()
        self.meta_verify_token = (meta_verify_token or "").strip()
        self.meta_app_secret = (meta_app_secret or "").strip()
        self.app = web.Application()
        self.app.router.add_post("/webhooks/trigger", self.handle_trigger)
        self.app.router.add_get("/webhooks/meta", self.handle_meta_verify)
        self.app.router.add_post("/webhooks/meta", self.handle_meta_event)

    async def handle_trigger(self, request: web.Request) -> web.Response:
        """Handle incoming webhook trigger."""
        if self.auth_token:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {self.auth_token}"
            if auth_header != expected:
                return web.Response(text="Unauthorized", status=401)

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
