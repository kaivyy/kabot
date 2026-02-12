"""Webhook Ingress Server."""
from aiohttp import web
from kabot.bus.queue import MessageBus
from kabot.bus.events import InboundMessage

class WebhookServer:
    def __init__(self, bus: MessageBus):
        self.bus = bus
        self.app = web.Application()
        self.app.router.add_post("/webhooks/trigger", self.handle_trigger)

    async def handle_trigger(self, request: web.Request) -> web.Response:
        """Handle incoming webhook trigger."""
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

    async def start(self, host: str = "0.0.0.0", port: int = 18790):
        """Start the webhook server."""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        return runner
