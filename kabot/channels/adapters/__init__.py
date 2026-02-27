"""Channel adapter registry exports."""

from .base import AdapterCapabilities, ChannelAdapterSpec
from .registry import AdapterRegistry, AdapterStatus

__all__ = [
    "AdapterCapabilities",
    "ChannelAdapterSpec",
    "AdapterRegistry",
    "AdapterStatus",
]

