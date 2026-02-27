"""Channel adapter contracts for registry-driven channel loading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from kabot.channels.base import BaseChannel


@dataclass(frozen=True)
class AdapterCapabilities:
    """Capabilities exposed by one adapter implementation."""

    production: bool = True
    experimental: bool = False
    supports_legacy: bool = True
    supports_instances: bool = True
    supports_health_check: bool = False


@dataclass(frozen=True)
class ChannelAdapterSpec:
    """Static registration metadata for one channel adapter."""

    key: str
    legacy_field: str | None
    config_model_path: str | None
    factory: Callable[[Any, Any, Any], BaseChannel]
    capabilities: AdapterCapabilities
    description: str = ""

