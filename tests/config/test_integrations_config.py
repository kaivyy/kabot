"""Tests for integration guard configuration defaults."""

from kabot.config.schema import Config


def test_integrations_defaults_are_safe():
    cfg = Config()
    assert cfg.integrations.http_guard.enabled is True
    assert cfg.integrations.http_guard.block_private_networks is True
    assert "169.254.169.254" in cfg.integrations.http_guard.deny_hosts
