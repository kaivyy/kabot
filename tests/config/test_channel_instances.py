"""Test channel instances configuration."""
import pytest
from kabot.config.schema import ChannelInstance, ChannelsConfig


def test_channel_instance_schema():
    """Test ChannelInstance schema."""
    instance = ChannelInstance(
        id="work_bot",
        type="telegram",
        enabled=True,
        config={"token": "123:ABC", "allow_from": []},
        agent_binding="work"
    )

    assert instance.id == "work_bot"
    assert instance.type == "telegram"
    assert instance.enabled is True
    assert instance.config["token"] == "123:ABC"
    assert instance.agent_binding == "work"


def test_channel_instance_optional_fields():
    """Test ChannelInstance with optional fields."""
    instance = ChannelInstance(
        id="simple_bot",
        type="discord",
        config={"token": "XYZ"}
    )

    assert instance.id == "simple_bot"
    assert instance.type == "discord"
    assert instance.enabled is True  # Default value
    assert instance.agent_binding is None  # Optional field


def test_channels_config_with_instances():
    """Test ChannelsConfig with instances list."""
    config = ChannelsConfig(
        instances=[
            ChannelInstance(
                id="work_tele",
                type="telegram",
                config={"token": "123:ABC", "allow_from": []}
            ),
            ChannelInstance(
                id="personal_tele",
                type="telegram",
                config={"token": "456:DEF", "allow_from": []}
            )
        ]
    )

    assert len(config.instances) == 2
    assert config.instances[0].id == "work_tele"
    assert config.instances[1].id == "personal_tele"


def test_channels_config_backward_compatibility():
    """Test that ChannelsConfig still supports legacy single-instance configs."""
    config = ChannelsConfig()

    # Should have default telegram config
    assert hasattr(config, 'telegram')
    assert hasattr(config, 'discord')
    assert hasattr(config, 'whatsapp')

    # Instances should default to empty list
    assert config.instances == []
