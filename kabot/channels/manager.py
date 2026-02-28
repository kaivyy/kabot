"""Channel manager for coordinating chat channels."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger

from kabot.bus.queue import MessageBus
from kabot.channels.adapters import AdapterRegistry
from kabot.channels.base import BaseChannel
from kabot.config.schema import Config

if TYPE_CHECKING:
    from kabot.session.manager import SessionManager


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Config, bus: MessageBus, session_manager: "SessionManager | None" = None):
        self.config = config
        self.bus = bus
        self.session_manager = session_manager
        self.adapter_registry = AdapterRegistry()
        self.channels: dict[str, BaseChannel] = {}
        self._instance_keys_by_type: dict[str, list[str]] = {}
        self._dispatch_task: asyncio.Task | None = None

        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize channels based on config."""

        # Process multi-instance configs first
        for instance in self.config.channels.instances:
            if not instance.enabled:
                continue

            channel_key = f"{instance.type}:{instance.id}"
            channel = self.adapter_registry.create_instance_channel(
                instance=instance,
                config=self.config,
                bus=self.bus,
                session_manager=self.session_manager,
            )
            if not channel:
                continue
            self._decorate_channel_security(channel)
            self._decorate_instance_channel(channel, channel_key, instance.type, instance.id, instance.agent_binding)
            self.channels[channel_key] = channel
            logger.info(f"{instance.type} instance '{instance.id}' enabled")

        # Then process legacy single-instance configs (backward compatibility)
        for status in self.adapter_registry.list_status():
            if not status.supports_legacy:
                continue
            channel = self.adapter_registry.create_legacy_channel(
                status.key,
                config=self.config,
                bus=self.bus,
                session_manager=self.session_manager,
            )
            if not channel:
                continue
            self._decorate_channel_security(channel)
            self.channels[status.key] = channel
            logger.info(f"{status.key} channel enabled")

    def _decorate_channel_security(self, channel: BaseChannel) -> None:
        """Attach global security preset so channels can enforce strict access policy."""
        preset = str(getattr(self.config.tools.exec, "policy_preset", "balanced") or "balanced").strip().lower()
        setattr(channel, "_security_policy_preset", preset)

    async def _start_channel(self, name: str, channel: BaseChannel) -> None:
        """Start a channel and log any exceptions."""
        try:
            await channel.start()
        except Exception as e:
            logger.error(f"Failed to start channel {name}: {e}")

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            return

        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # Start channels
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"Starting {name} channel...")
            tasks.append(asyncio.create_task(self._start_channel(name, channel)))

        # Wait for all to complete (they should run forever)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")

        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )

                channel = self.channels.get(msg.channel)
                if not channel and ":" not in msg.channel:
                    candidates = self._instance_keys_by_type.get(msg.channel, [])
                    if len(candidates) == 1:
                        channel = self.channels.get(candidates[0])
                    elif len(candidates) > 1:
                        logger.warning(
                            f"Ambiguous channel '{msg.channel}' with {len(candidates)} instances; "
                            "send using explicit key '<type>:<id>'."
                        )
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                else:
                    logger.warning(f"Unknown channel: {msg.channel}")

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def _decorate_instance_channel(
        self,
        channel: BaseChannel,
        channel_key: str,
        channel_type: str,
        instance_id: str,
        agent_binding: str | None,
    ) -> None:
        """Attach instance metadata so inbound routing can preserve instance identity."""
        setattr(channel, "_channel_name", channel_key)
        setattr(
            channel,
            "_channel_instance_metadata",
            {
                "id": instance_id,
                "type": channel_type,
                "agent_binding": agent_binding,
            },
        )
        self._instance_keys_by_type.setdefault(channel_type, []).append(channel_key)

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running
            }
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())
