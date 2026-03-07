"""Webhook ingress handlers: trigger, Meta verify, Meta event."""

from __future__ import annotations

from aiohttp import web

from kabot.bus.events import InboundMessage
from kabot.integrations.meta_webhook import parse_meta_inbound, verify_meta_signature


class WebhookMixin:

    async def handle_trigger(self, request: web.Request) -> web.Response:
        """Handle incoming webhook trigger."""
        unauthorized = self._authorize_route(request)
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
        unauthorized = self._authorize_route(request)
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
