# Multi-Channel Instances Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable configuration and operation of multiple bot instances per platform (e.g., 4 Telegram bots, 4 Discord bots)

**Architecture:** Extend config schema to support named channel instances while maintaining backward compatibility. Update ChannelManager to instantiate multiple instances with unique identifiers.

**Tech Stack:** Pydantic, asyncio, existing channel implementations

---

## Phase 1: Config Schema Extension

### Task 1: Channel Instance Schema

**Files:**
- Modify: `kabot/config/schema.py`
- Test: `tests/config/test_channel_instances.py`

**Step 1: Write failing test**

```python
def test_channel_instance_schema():
    """Test ChannelInstance schema."""
    from kabot.config.schema import ChannelInstance

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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/config/test_channel_instances.py::test_channel_instance_schema -v`
Expected: FAIL with "No module named 'ChannelInstance'"

**Step 3: Implement ChannelInstance schema**

```python
class ChannelInstance(BaseModel):
    """A single channel instance configuration."""
    id: str  # Unique identifier (e.g., "work_bot", "personal_bot")
    type: str  # Channel type ("telegram", "discord", "whatsapp", etc.)
    enabled: bool = True
    config: dict[str, Any]  # Type-specific configuration
    agent_binding: str | None = None  # Optional agent binding
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/config/test_channel_instances.py::test_channel_instance_schema -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/config/test_channel_instances.py kabot/config/schema.py
git commit -m "feat(config): add ChannelInstance schema for multi-channel support"
```

### Task 2: Extend ChannelsConfig

**Files:**
- Modify: `kabot/config/schema.py`
- Test: `tests/config/test_channel_instances.py`

**Step 1: Write failing test**

```python
def test_channels_config_with_instances():
    """Test ChannelsConfig with instances list."""
    from kabot.config.schema import ChannelsConfig, ChannelInstance

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
```

**Step 2: Run test**

Expected: FAIL

**Step 3: Implement**

Add `instances` field to ChannelsConfig:

```python
class ChannelsConfig(BaseModel):
    # Existing single-instance configs (backward compatibility)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    # ... other channels ...

    # New multi-instance support
    instances: list[ChannelInstance] = Field(default_factory=list)
```

**Step 4: Run test**

Expected: PASS

**Step 5: Commit**

```bash
git add tests/config/test_channel_instances.py kabot/config/schema.py
git commit -m "feat(config): add instances list to ChannelsConfig"
```

## Phase 2: Channel Manager Updates

### Task 3: Multi-Instance Channel Manager

**Files:**
- Modify: `kabot/channels/manager.py`
- Test: `tests/channels/test_multi_instance_manager.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_channel_manager_multiple_telegram_instances():
    """Test ChannelManager with multiple Telegram instances."""
    from kabot.config.schema import Config, ChannelsConfig, ChannelInstance
    from kabot.channels.manager import ChannelManager
    from kabot.bus.queue import MessageBus

    config = Config()
    config.channels = ChannelsConfig(
        instances=[
            ChannelInstance(
                id="work_bot",
                type="telegram",
                enabled=True,
                config={"token": "123:ABC", "allow_from": []}
            ),
            ChannelInstance(
                id="personal_bot",
                type="telegram",
                enabled=True,
                config={"token": "456:DEF", "allow_from": []}
            )
        ]
    )

    bus = MessageBus()
    manager = ChannelManager(config, bus)

    # Should have 2 telegram instances
    assert "telegram:work_bot" in manager.channels
    assert "telegram:personal_bot" in manager.channels
    assert len(manager.channels) == 2
```

**Step 2: Run test**

Expected: FAIL

**Step 3: Implement multi-instance support**

Update `_init_channels()` to process instances:

```python
def _init_channels(self) -> None:
    """Initialize channels based on config."""

    # Process multi-instance configs first
    for instance in self.config.channels.instances:
        if not instance.enabled:
            continue

        channel_key = f"{instance.type}:{instance.id}"

        try:
            if instance.type == "telegram":
                from kabot.channels.telegram import TelegramChannel
                from kabot.config.schema import TelegramConfig

                # Convert dict config to TelegramConfig
                tele_config = TelegramConfig(**instance.config)
                self.channels[channel_key] = TelegramChannel(
                    tele_config,
                    self.bus,
                    groq_api_key=self.config.providers.groq.api_key,
                    session_manager=self.session_manager,
                )
                logger.info(f"Telegram instance '{instance.id}' enabled")

            elif instance.type == "discord":
                from kabot.channels.discord import DiscordChannel
                from kabot.config.schema import DiscordConfig

                discord_config = DiscordConfig(**instance.config)
                self.channels[channel_key] = DiscordChannel(
                    discord_config,
                    self.bus
                )
                logger.info(f"Discord instance '{instance.id}' enabled")

            # Add other channel types as needed

        except ImportError as e:
            logger.warning(f"{instance.type} channel not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize {instance.type}:{instance.id}: {e}")

    # Then process legacy single-instance configs (backward compatibility)
    # ... existing code ...
```

**Step 4: Run test**

Expected: PASS

**Step 5: Commit**

```bash
git add tests/channels/test_multi_instance_manager.py kabot/channels/manager.py
git commit -m "feat(channels): support multiple instances per channel type"
```

## Phase 3: Setup Wizard Updates

### Task 4: Multi-Channel Setup Wizard

**Files:**
- Modify: `kabot/cli/setup_wizard.py`
- Test: Manual testing (interactive CLI)

**Step 1: Add channel instances menu**

Add new menu option after LLM configuration:

```python
def configure_channel_instances(c: Config) -> None:
    """Configure multiple channel instances."""
    console.print("\n[bold cyan]═══ Channel Instances Configuration ═══[/bold cyan]\n")

    while True:
        # Show current instances
        if c.channels.instances:
            console.print("[bold]Current Instances:[/bold]")
            for idx, inst in enumerate(c.channels.instances, 1):
                status = "✓" if inst.enabled else "✗"
                binding = f" → {inst.agent_binding}" if inst.agent_binding else ""
                console.print(f"  {idx}. [{inst.type}] {inst.id} {status}{binding}")
            console.print()

        choice = Prompt.ask(
            "│  Action",
            choices=["add", "edit", "delete", "done"],
            default="done"
        )

        if choice == "add":
            add_channel_instance(c)
        elif choice == "edit":
            edit_channel_instance(c)
        elif choice == "delete":
            delete_channel_instance(c)
        elif choice == "done":
            break
```

**Step 2: Implement add_channel_instance**

```python
def add_channel_instance(c: Config) -> None:
    """Add a new channel instance."""
    instance_id = Prompt.ask("│  Instance ID (e.g., work_bot, personal_bot)")

    channel_type = Prompt.ask(
        "│  Channel Type",
        choices=["telegram", "discord", "whatsapp", "slack"],
        default="telegram"
    )

    # Get type-specific configuration
    config_dict = {}

    if channel_type == "telegram":
        token = Prompt.ask("│  Bot Token")
        config_dict = {"token": token, "allow_from": []}

    elif channel_type == "discord":
        token = Prompt.ask("│  Bot Token")
        config_dict = {"token": token, "allow_from": []}

    # Optional agent binding
    if c.agents.agents:
        bind_agent = Confirm.ask("│  Bind to specific agent?", default=False)
        agent_binding = None
        if bind_agent:
            agent_ids = [a.id for a in c.agents.agents]
            agent_binding = Prompt.ask("│  Agent ID", choices=agent_ids)
    else:
        agent_binding = None

    # Create instance
    from kabot.config.schema import ChannelInstance
    instance = ChannelInstance(
        id=instance_id,
        type=channel_type,
        enabled=True,
        config=config_dict,
        agent_binding=agent_binding
    )

    c.channels.instances.append(instance)
    console.print(f"[green]✓[/green] Added {channel_type} instance '{instance_id}'")
```

**Step 3: Implement edit and delete functions**

```python
def edit_channel_instance(c: Config) -> None:
    """Edit an existing channel instance."""
    if not c.channels.instances:
        console.print("[yellow]No instances configured[/yellow]")
        return

    # Show instances with numbers
    for idx, inst in enumerate(c.channels.instances, 1):
        console.print(f"  {idx}. [{inst.type}] {inst.id}")

    idx = IntPrompt.ask("│  Instance number to edit", default=1)
    if 1 <= idx <= len(c.channels.instances):
        instance = c.channels.instances[idx - 1]

        # Edit enabled status
        instance.enabled = Confirm.ask(
            f"│  Enable {instance.id}?",
            default=instance.enabled
        )

        # Edit agent binding
        if c.agents.agents:
            change_binding = Confirm.ask("│  Change agent binding?", default=False)
            if change_binding:
                agent_ids = ["none"] + [a.id for a in c.agents.agents]
                binding = Prompt.ask("│  Agent ID", choices=agent_ids, default="none")
                instance.agent_binding = None if binding == "none" else binding

        console.print(f"[green]✓[/green] Updated {instance.id}")


def delete_channel_instance(c: Config) -> None:
    """Delete a channel instance."""
    if not c.channels.instances:
        console.print("[yellow]No instances configured[/yellow]")
        return

    for idx, inst in enumerate(c.channels.instances, 1):
        console.print(f"  {idx}. [{inst.type}] {inst.id}")

    idx = IntPrompt.ask("│  Instance number to delete", default=1)
    if 1 <= idx <= len(c.channels.instances):
        instance = c.channels.instances[idx - 1]
        if Confirm.ask(f"│  Delete {instance.id}?", default=False):
            c.channels.instances.pop(idx - 1)
            console.print(f"[green]✓[/green] Deleted {instance.id}")
```

**Step 4: Integrate into main wizard flow**

Add call to `configure_channel_instances(c)` after LLM configuration in `run_wizard()`.

**Step 5: Manual testing**

Run: `kabot config`
Test: Add/edit/delete channel instances

**Step 6: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat(cli): add multi-channel instance configuration to setup wizard"
```

## Phase 4: Documentation

### Task 5: Update README

**Files:**
- Modify: `README.md`

Add section explaining multi-channel instances:

```markdown
### Multi-Channel Instances

Run multiple bots per platform with different configurations:

```json
{
  "channels": {
    "instances": [
      {
        "id": "work_bot",
        "type": "telegram",
        "enabled": true,
        "config": {
          "token": "123:ABC",
          "allow_from": []
        },
        "agent_binding": "work"
      },
      {
        "id": "personal_bot",
        "type": "telegram",
        "enabled": true,
        "config": {
          "token": "456:DEF",
          "allow_from": []
        },
        "agent_binding": "personal"
      }
    ]
  }
}
```

Each instance can be bound to a specific agent for context separation.
```

**Commit:**

```bash
git add README.md
git commit -m "docs: add multi-channel instances documentation"
```

---

## Testing Strategy

1. Unit tests for schema validation
2. Integration tests for ChannelManager with multiple instances
3. Manual testing of setup wizard
4. End-to-end test with 2 Telegram bots running simultaneously

## Backward Compatibility

- Existing single-channel configs continue to work
- `instances` list is optional (defaults to empty)
- Legacy channel configs are processed after instances
- No breaking changes to existing deployments
