"""Configuration module for kabot."""

from kabot.config.loader import get_config_path, load_config
from kabot.config.schema import Config

__all__ = ["Config", "load_config", "get_config_path"]
