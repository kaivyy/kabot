"""Registry-driven channel adapter loading."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from loguru import logger

from kabot.channels.adapters.base import AdapterCapabilities, ChannelAdapterSpec
from kabot.config.schema import ChannelInstance, Config


def _factory_from_path(module_path: str, class_name: str, *, telegram: bool = False):
    def _factory(
        channel_cfg: Any,
        config: Config,
        bus: Any,
        session_manager: Any | None = None,
        command_router: Any | None = None,
    ):
        module = importlib.import_module(module_path)
        channel_cls = getattr(module, class_name)
        if telegram:
            return channel_cls(
                channel_cfg,
                bus,
                groq_api_key=config.providers.groq.api_key,
                session_manager=session_manager,
                command_router=command_router,
                workspace=config.agents.defaults.workspace,
            )
        if class_name == "WhatsAppChannel":
            return channel_cls(channel_cfg, bus)
        return channel_cls(channel_cfg, bus)

    return _factory


def _placeholder_factory(
    channel_cfg: Any,
    config: Config,
    bus: Any,
    session_manager: Any | None = None,
    command_router: Any | None = None,
):
    raise NotImplementedError("Adapter implementation not available in this build")


@dataclass(frozen=True)
class AdapterStatus:
    key: str
    enabled: bool
    production: bool
    experimental: bool
    supports_instances: bool
    supports_legacy: bool
    description: str


class AdapterRegistry:
    """Adapter registry with production/experimental capability flags."""

    def __init__(self, feature_flags: dict[str, bool] | None = None):
        self.feature_flags = feature_flags or {}
        self._specs: dict[str, ChannelAdapterSpec] = {}
        self._register_builtin_specs()

    def register(self, spec: ChannelAdapterSpec) -> None:
        self._specs[spec.key] = spec

    def get(self, key: str) -> ChannelAdapterSpec | None:
        return self._specs.get(key)

    def _is_enabled(self, spec: ChannelAdapterSpec) -> bool:
        if spec.key in self.feature_flags:
            return bool(self.feature_flags.get(spec.key))
        if not spec.capabilities.experimental:
            return True
        return bool(self.feature_flags.get(spec.key, False))

    def list_status(self) -> list[AdapterStatus]:
        statuses: list[AdapterStatus] = []
        for key in sorted(self._specs):
            spec = self._specs[key]
            statuses.append(
                AdapterStatus(
                    key=spec.key,
                    enabled=self._is_enabled(spec),
                    production=spec.capabilities.production,
                    experimental=spec.capabilities.experimental,
                    supports_instances=spec.capabilities.supports_instances,
                    supports_legacy=spec.capabilities.supports_legacy,
                    description=spec.description,
                )
            )
        return statuses

    def create_legacy_channel(
        self,
        key: str,
        config: Config,
        bus: Any,
        session_manager: Any | None = None,
        command_router: Any | None = None,
    ) -> Any | None:
        spec = self.get(key)
        if not spec:
            return None
        if not self._is_enabled(spec):
            logger.debug(f"Adapter '{key}' disabled by feature flag")
            return None
        if not spec.capabilities.supports_legacy or not spec.legacy_field:
            return None

        channel_cfg = getattr(config.channels, spec.legacy_field, None)
        if not channel_cfg or not getattr(channel_cfg, "enabled", False):
            return None

        try:
            return spec.factory(channel_cfg, config, bus, session_manager, command_router)
        except Exception as exc:
            logger.warning(f"{key} adapter not available: {exc}")
            return None

    def create_instance_channel(
        self,
        instance: ChannelInstance,
        config: Config,
        bus: Any,
        session_manager: Any | None = None,
        command_router: Any | None = None,
    ) -> Any | None:
        spec = self.get(instance.type)
        if not spec:
            logger.warning(f"Unknown channel type: {instance.type}")
            return None
        if not self._is_enabled(spec):
            logger.warning(f"Channel '{instance.type}' is experimental and disabled by flag")
            return None
        if not spec.capabilities.supports_instances:
            logger.warning(f"Channel '{instance.type}' does not support multi-instance mode")
            return None

        channel_cfg = instance.config
        if spec.config_model_path:
            try:
                model_module, model_name = spec.config_model_path.rsplit(".", 1)
                cfg_model = getattr(importlib.import_module(model_module), model_name)
                channel_cfg = cfg_model(**instance.config)
            except Exception as exc:
                logger.error(f"Invalid instance config for {instance.type}:{instance.id}: {exc}")
                return None

        try:
            return spec.factory(channel_cfg, config, bus, session_manager, command_router)
        except Exception as exc:
            logger.warning(f"Failed to initialize {instance.type}:{instance.id}: {exc}")
            return None

    def _register_builtin_specs(self) -> None:
        production = AdapterCapabilities(production=True, experimental=False)
        experimental = AdapterCapabilities(production=False, experimental=True)

        # Production adapters currently implemented in Kabot.
        self.register(
            ChannelAdapterSpec(
                key="telegram",
                legacy_field="telegram",
                config_model_path="kabot.config.schema.TelegramConfig",
                factory=_factory_from_path("kabot.channels.telegram", "TelegramChannel", telegram=True),
                capabilities=production,
                description="Telegram bot adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="whatsapp",
                legacy_field="whatsapp",
                config_model_path="kabot.config.schema.WhatsAppConfig",
                factory=_factory_from_path("kabot.channels.whatsapp", "WhatsAppChannel"),
                capabilities=production,
                description="WhatsApp bridge adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="discord",
                legacy_field="discord",
                config_model_path="kabot.config.schema.DiscordConfig",
                factory=_factory_from_path("kabot.channels.discord", "DiscordChannel"),
                capabilities=production,
                description="Discord gateway adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="slack",
                legacy_field="slack",
                config_model_path="kabot.config.schema.SlackConfig",
                factory=_factory_from_path("kabot.channels.slack", "SlackChannel"),
                capabilities=production,
                description="Slack adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="email",
                legacy_field="email",
                config_model_path="kabot.config.schema.EmailConfig",
                factory=_factory_from_path("kabot.channels.email", "EmailChannel"),
                capabilities=production,
                description="Email adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="feishu",
                legacy_field="feishu",
                config_model_path="kabot.config.schema.FeishuConfig",
                factory=_factory_from_path("kabot.channels.feishu", "FeishuChannel"),
                capabilities=production,
                description="Feishu adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="dingtalk",
                legacy_field="dingtalk",
                config_model_path="kabot.config.schema.DingTalkConfig",
                factory=_factory_from_path("kabot.channels.dingtalk", "DingTalkChannel"),
                capabilities=production,
                description="DingTalk adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="qq",
                legacy_field="qq",
                config_model_path="kabot.config.schema.QQConfig",
                factory=_factory_from_path("kabot.channels.qq", "QQChannel"),
                capabilities=production,
                description="QQ adapter",
            )
        )

        # Target top-15 production keys scaffolded for future implementation.
        self.register(
            ChannelAdapterSpec(
                key="signal",
                legacy_field=None,
                config_model_path="kabot.config.schema.SignalConfig",
                factory=_factory_from_path("kabot.channels.signal", "SignalChannel"),
                capabilities=production,
                description="Signal bridge adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="matrix",
                legacy_field=None,
                config_model_path="kabot.config.schema.MatrixConfig",
                factory=_factory_from_path("kabot.channels.matrix", "MatrixChannel"),
                capabilities=production,
                description="Matrix bridge adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="teams",
                legacy_field=None,
                config_model_path="kabot.config.schema.TeamsConfig",
                factory=_factory_from_path("kabot.channels.teams", "TeamsChannel"),
                capabilities=production,
                description="Teams bridge adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="google_chat",
                legacy_field=None,
                config_model_path="kabot.config.schema.GoogleChatConfig",
                factory=_factory_from_path("kabot.channels.google_chat", "GoogleChatChannel"),
                capabilities=production,
                description="Google Chat bridge adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="mattermost",
                legacy_field=None,
                config_model_path="kabot.config.schema.MattermostConfig",
                factory=_factory_from_path("kabot.channels.mattermost", "MattermostChannel"),
                capabilities=production,
                description="Mattermost bridge adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="webex",
                legacy_field=None,
                config_model_path="kabot.config.schema.WebexConfig",
                factory=_factory_from_path("kabot.channels.webex", "WebexChannel"),
                capabilities=production,
                description="Webex bridge adapter",
            )
        )
        self.register(
            ChannelAdapterSpec(
                key="line",
                legacy_field=None,
                config_model_path="kabot.config.schema.LineConfig",
                factory=_factory_from_path("kabot.channels.line", "LineChannel"),
                capabilities=production,
                description="LINE bridge adapter",
            )
        )

        # Experimental adapters (disabled unless explicitly feature-flagged).
        for key in [
            "irc",
            "xmpp",
            "zulip",
            "twitch",
            "bluesky",
            "mastodon",
            "messenger",
            "reddit",
            "revolt",
            "viber",
            "flock",
            "guilded",
            "keybase",
            "nextcloud_chat",
            "nostr",
            "pumble",
            "threema",
            "twist",
            "discourse",
            "gitter",
            "gotify",
            "linkedin_messaging",
            "mumble",
            "ntfy",
            "webhook_inbound",
        ]:
            self.register(
                ChannelAdapterSpec(
                    key=key,
                    legacy_field=None,
                    config_model_path=None,
                    factory=_placeholder_factory,
                    capabilities=experimental,
                    description=f"{key} adapter (experimental)",
                )
            )
