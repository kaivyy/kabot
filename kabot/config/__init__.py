"""Configuration module for kabot."""

from kabot.config.loader import load_config, get_config_path
from kabot.config.schema import Config

__all__ = ["Config", "load_config", "get_config_path"]
