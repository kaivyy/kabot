# Phase 1: OpenClaw-Style Multi-Agent Implementation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement OpenClaw-style multi-agent system with context separation (work/personal/family agents)

**Architecture:** Multiple independent agents with separate workspaces, per-agent model assignment, message routing via binding system, CLI management commands

**Tech Stack:** Python 3.11+, Pydantic, asyncio, Typer CLI, existing Kabot MessageBus/SessionManager

---

## Task 1: Agent Configuration Schema

**Files:**
- Modify: `kabot/config/schema.py:1-50`
- Test: `tests/config/test_agent_config.py`

**Step 1: Write failing test**

```python
# tests/config/test_agent_config.py
def test_agent_config_schema():
    from kabot.config.schema import AgentConfig, AgentsConfig

    config = AgentConfig(
        id="work",
        name="Work Agent",
        model="openai/gpt-4o",
        workspace="~/.kabot/workspace-work"
    )
    assert config.id == "work"
    assert config.model == "openai/gpt-4o"

def test_agents_config_with_list():
    from kabot.config.schema import AgentsConfig, AgentConfig

    agents = AgentsConfig(
        list=[
            AgentConfig(id="work", name="Work", model="openai/gpt-4o"),
            AgentConfig(id="personal", name="Personal", model="anthropic/claude-sonnet-4-5")
        ]
    )
    assert len(agents.list) == 2
```

**Step 2: Run test**

Run: `pytest tests/config/test_agent_config.py -v`
Expected: FAIL (AgentConfig not defined)

**Step 3: Implement schema**

```python
# kabot/config/schema.py (add after existing imports)
class AgentConfig(BaseModel):
    id: str
    name: str = ""
    model: str | None = None
    workspace: str | None = None
    default: bool = False

class AgentsConfig(BaseModel):
    list: list[AgentConfig] = Field(default_factory=list)

# Modify Config class to include agents
class Config(BaseSettings):
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    # ... existing fields ...
```

**Step 4: Run test**

Run: `pytest tests/config/test_agent_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/config/schema.py tests/config/test_agent_config.py
git commit -m "feat(config): add agent configuration schema

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Agent Registry

**Files:**
- Create: `kabot/agent/agent_registry.py`
- Test: `tests/agent/test_agent_registry.py`

**Step 1: Write failing test**

```python
# tests/agent/test_agent_registry.py
import pytest
from pathlib import Path

def test_registry_initialization(tmp_path):
    from kabot.agent.agent_registry import AgentRegistry

    registry_path = tmp_path / "agents" / "registry.json"
    registry = AgentRegistry(registry_path)

    assert registry_path.exists()
    agents = registry.list_agents()
    assert agents == []

def test_register_agent(tmp_path):
    from kabot.agent.agent_registry import AgentRegistry

    registry = AgentRegistry(tmp_path / "registry.json")
    registry.register("work", "Work Agent", "openai/gpt-4o", "~/.kabot/workspace-work")

    agent = registry.get("work")
    assert agent["id"] == "work"
    assert agent["model"] == "openai/gpt-4o"
```

**Step 2: Run test**

Run: `pytest tests/agent/test_agent_registry.py -v`
Expected: FAIL (AgentRegistry not defined)

**Step 3: Implement registry**

```python
# kabot/agent/agent_registry.py
import json
from pathlib import Path
from typing import Any

class AgentRegistry:
    def __init__(self, registry_path: Path):
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._save({"agents": {}})

    def _load(self) -> dict[str, Any]:
        with open(self.registry_path) as f:
            return json.load(f)

    def _save(self, data: dict[str, Any]) -> None:
        with open(self.registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def register(self, agent_id: str, name: str, model: str, workspace: str) -> None:
        data = self._load()
        data["agents"][agent_id] = {
            "id": agent_id,
            "name": name,
            "model": model,
            "workspace": workspace
        }
        self._save(data)

    def get(self, agent_id: str) -> dict[str, Any] | None:
        data = self._load()
        return data["agents"].get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        data = self._load()
        return list(data["agents"].values())
```

**Step 4: Run test**

Run: `pytest tests/agent/test_agent_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/agent_registry.py tests/agent/test_agent_registry.py
git commit -m "feat(agent): implement agent registry with persistence

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Agent Scope Resolution

**Files:**
- Create: `kabot/agent/agent_scope.py`
- Test: `tests/agent/test_agent_scope.py`

**Step 1: Write failing test**

```python
# tests/agent/test_agent_scope.py
def test_resolve_default_agent():
    from kabot.agent.agent_scope import resolve_default_agent_id
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(list=[
        AgentConfig(id="work", default=True),
        AgentConfig(id="personal")
    ]))

    assert resolve_default_agent_id(config) == "work"

def test_resolve_agent_workspace():
    from kabot.agent.agent_scope import resolve_agent_workspace
    from kabot.config.schema import Config, AgentsConfig, AgentConfig

    config = Config(agents=AgentsConfig(list=[
        AgentConfig(id="work", workspace="~/.kabot/workspace-work")
    ]))

    workspace = resolve_agent_workspace(config, "work")
    assert "workspace-work" in str(workspace)
```

**Step 2: Run test**

Run: `pytest tests/agent/test_agent_scope.py -v`
Expected: FAIL

**Step 3: Implement scope resolution**

```python
# kabot/agent/agent_scope.py
from pathlib import Path
from kabot.config.schema import Config

def resolve_default_agent_id(config: Config) -> str:
    for agent in config.agents.list:
        if agent.default:
            return agent.id
    return "main"

def resolve_agent_config(config: Config, agent_id: str):
    for agent in config.agents.list:
        if agent.id == agent_id:
            return agent
    return None

def resolve_agent_workspace(config: Config, agent_id: str) -> Path:
    agent = resolve_agent_config(config, agent_id)
    if agent and agent.workspace:
        return Path(agent.workspace).expanduser()
    return Path.home() / ".kabot" / f"workspace-{agent_id}"

def resolve_agent_model(config: Config, agent_id: str) -> str | None:
    agent = resolve_agent_config(config, agent_id)
    return agent.model if agent else None
```

**Step 4: Run test**

Run: `pytest tests/agent/test_agent_scope.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/agent_scope.py tests/agent/test_agent_scope.py
git commit -m "feat(agent): implement agent scope resolution

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Session Key Format

**Files:**
- Create: `kabot/session/session_key.py`
- Test: `tests/session/test_session_key.py`

**Step 1: Write failing test**

```python
# tests/session/test_session_key.py
def test_build_agent_session_key():
    from kabot.session.session_key import build_agent_session_key

    key = build_agent_session_key("work", "telegram", "123456")
    assert key == "agent:work:telegram:123456"

def test_parse_agent_session_key():
    from kabot.session.session_key import parse_agent_session_key

    parsed = parse_agent_session_key("agent:work:telegram:123456")
    assert parsed["agent_id"] == "work"
    assert parsed["channel"] == "telegram"
    assert parsed["chat_id"] == "123456"
```

**Step 2: Run test**

Run: `pytest tests/session/test_session_key.py -v`
Expected: FAIL

**Step 3: Implement session key**

```python
# kabot/session/session_key.py
def build_agent_session_key(agent_id: str, channel: str, chat_id: str) -> str:
    return f"agent:{agent_id}:{channel}:{chat_id}"

def parse_agent_session_key(session_key: str) -> dict[str, str]:
    parts = session_key.split(":")
    if len(parts) >= 4 and parts[0] == "agent":
        return {
            "agent_id": parts[1],
            "channel": parts[2],
            "chat_id": ":".join(parts[3:])
        }
    return {}
```

**Step 4: Run test**

Run: `pytest tests/session/test_session_key.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/session/session_key.py tests/session/test_session_key.py
git commit -m "feat(session): implement agent session key format

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Binding System

**Files:**
- Create: `kabot/routing/bindings.py`
- Modify: `kabot/config/schema.py:50-70`
- Test: `tests/routing/test_bindings.py`

**Step 1: Write failing test**

```python
# tests/routing/test_bindings.py
def test_resolve_agent_by_channel():
    from kabot.routing.bindings import resolve_agent_route
    from kabot.config.schema import Config, AgentsConfig, AgentConfig, AgentBinding

    config = Config(
        agents=AgentsConfig(
            list=[AgentConfig(id="work"), AgentConfig(id="personal", default=True)],
            bindings=[AgentBinding(agent_id="work", channel="telegram")]
        )
    )

    agent_id = resolve_agent_route(config, "telegram", "123456")
    assert agent_id == "work"

    agent_id = resolve_agent_route(config, "whatsapp", "789")
    assert agent_id == "personal"  # fallback to default
```

**Step 2: Run test**

Run: `pytest tests/routing/test_bindings.py -v`
Expected: FAIL

**Step 3: Add binding schema**

```python
# kabot/config/schema.py (add after AgentConfig)
class AgentBinding(BaseModel):
    agent_id: str
    channel: str
    chat_id: str | None = None

class AgentsConfig(BaseModel):
    list: list[AgentConfig] = Field(default_factory=list)
    bindings: list[AgentBinding] = Field(default_factory=list)
```

**Step 4: Implement binding resolution**

```python
# kabot/routing/bindings.py
from kabot.config.schema import Config
from kabot.agent.agent_scope import resolve_default_agent_id

def resolve_agent_route(config: Config, channel: str, chat_id: str) -> str:
    # Priority 1: Exact channel + chat_id match
    for binding in config.agents.bindings:
        if binding.channel == channel and binding.chat_id == chat_id:
            return binding.agent_id

    # Priority 2: Channel-only match
    for binding in config.agents.bindings:
        if binding.channel == channel and binding.chat_id is None:
            return binding.agent_id

    # Priority 3: Default agent
    return resolve_default_agent_id(config)
```

**Step 5: Run test**

Run: `pytest tests/routing/test_bindings.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add kabot/routing/bindings.py kabot/config/schema.py tests/routing/test_bindings.py
git commit -m "feat(routing): implement binding system for agent routing

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Integrate with AgentLoop

**Files:**
- Modify: `kabot/agent/loop.py:70-100`
- Test: `tests/agent/test_loop_multi_agent.py`

**Step 1: Write failing test**

```python
# tests/agent/test_loop_multi_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_agent_loop_routes_to_correct_agent(tmp_path):
    from kabot.agent.loop import AgentLoop
    from kabot.bus.queue import MessageBus
    from kabot.bus.events import InboundMessage
    from kabot.config.schema import Config, AgentsConfig, AgentConfig, AgentBinding

    config = Config(
        agents=AgentsConfig(
            list=[
                AgentConfig(id="work", model="openai/gpt-4o", workspace=str(tmp_path / "work")),
                AgentConfig(id="personal", model="anthropic/claude-sonnet-4-5", default=True)
            ],
            bindings=[AgentBinding(agent_id="work", channel="telegram")]
        )
    )

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="openai/gpt-4o")

    loop = AgentLoop(bus, provider, tmp_path, config=config)

    msg = InboundMessage(
        channel="telegram",
        sender_id="user1",
        chat_id="123",
        content="Hello",
        timestamp=None
    )

    # Should route to work agent
    session_key = loop._get_session_key(msg)
    assert "work" in session_key
```

**Step 2: Run test**

Run: `pytest tests/agent/test_loop_multi_agent.py -v`
Expected: FAIL

**Step 3: Modify AgentLoop**

```python
# kabot/agent/loop.py (modify __init__)
class AgentLoop:
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        config: Config | None = None,  # Add config parameter
        # ... existing parameters ...
    ):
        self.config = config or Config()
        # ... existing initialization ...

    def _get_session_key(self, msg: InboundMessage) -> str:
        """Get session key with agent routing."""
        from kabot.routing.bindings import resolve_agent_route
        from kabot.session.session_key import build_agent_session_key

        agent_id = resolve_agent_route(self.config, msg.channel, msg.chat_id)
        return build_agent_session_key(agent_id, msg.channel, msg.chat_id)

    async def _init_session(self, msg: InboundMessage) -> Any:
        session_key = self._get_session_key(msg)
        # ... rest of existing code ...
```

**Step 4: Run test**

Run: `pytest tests/agent/test_loop_multi_agent.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop.py tests/agent/test_loop_multi_agent.py
git commit -m "feat(agent): integrate multi-agent routing into agent loop

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: CLI Commands

**Files:**
- Create: `kabot/cli/agents.py`
- Modify: `kabot/cli/commands.py:1-20`
- Test: Manual testing

**Step 1: Implement agents CLI**

```python
# kabot/cli/agents.py
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage multi-agent configuration")
console = Console()

@app.command("list")
def list_agents():
    """List all configured agents."""
    from kabot.config.loader import load_config

    config = load_config()

    if not config.agents.list:
        console.print("[yellow]No agents configured[/yellow]")
        return

    table = Table(title="Configured Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Model", style="blue")
    table.add_column("Default", style="magenta")

    for agent in config.agents.list:
        table.add_row(
            agent.id,
            agent.name or "-",
            agent.model or "-",
            "✓" if agent.default else ""
        )

    console.print(table)

@app.command("add")
def add_agent(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    name: str = typer.Option("", help="Agent name"),
    model: str = typer.Option("", help="Model to use"),
    workspace: str = typer.Option("", help="Workspace directory"),
    default: bool = typer.Option(False, help="Set as default agent"),
):
    """Add a new agent."""
    from kabot.config.loader import load_config, save_config
    from kabot.config.schema import AgentConfig

    config = load_config()

    # Check if agent already exists
    if any(a.id == agent_id for a in config.agents.list):
        console.print(f"[red]Agent '{agent_id}' already exists[/red]")
        raise typer.Exit(1)

    # Create workspace directory
    workspace_path = Path(workspace).expanduser() if workspace else Path.home() / ".kabot" / f"workspace-{agent_id}"
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Add agent
    new_agent = AgentConfig(
        id=agent_id,
        name=name or agent_id.title(),
        model=model or None,
        workspace=str(workspace_path),
        default=default
    )
    config.agents.list.append(new_agent)

    save_config(config)
    console.print(f"[green]✓[/green] Agent '{agent_id}' added")

@app.command("delete")
def delete_agent(
    agent_id: str = typer.Argument(..., help="Agent ID to delete"),
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Delete an agent."""
    from kabot.config.loader import load_config, save_config

    config = load_config()

    # Find agent
    agent = next((a for a in config.agents.list if a.id == agent_id), None)
    if not agent:
        console.print(f"[red]Agent '{agent_id}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete agent '{agent_id}'?")
        if not confirm:
            raise typer.Abort()

    # Remove agent
    config.agents.list = [a for a in config.agents.list if a.id != agent_id]
    save_config(config)

    console.print(f"[green]✓[/green] Agent '{agent_id}' deleted")
```

**Step 2: Register CLI commands**

```python
# kabot/cli/commands.py (add import and registration)
from kabot.cli import agents

app.add_typer(agents.app, name="agents")
```

**Step 3: Test manually**

Run: `kabot agents list`
Expected: Shows configured agents or "No agents configured"

Run: `kabot agents add work --name "Work Agent" --model openai/gpt-4o`
Expected: Agent created successfully

Run: `kabot agents list`
Expected: Shows work agent

**Step 4: Commit**

```bash
git add kabot/cli/agents.py kabot/cli/commands.py
git commit -m "feat(cli): add agents management commands

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Integration Testing

**Files:**
- Create: `tests/integration/test_multi_agent_flow.py`

**Step 1: Write integration test**

```python
# tests/integration/test_multi_agent_flow.py
import pytest
from pathlib import Path

@pytest.mark.asyncio
async def test_full_multi_agent_flow(tmp_path):
    """Test complete multi-agent flow from config to routing."""
    from kabot.config.schema import Config, AgentsConfig, AgentConfig, AgentBinding
    from kabot.routing.bindings import resolve_agent_route
    from kabot.session.session_key import build_agent_session_key
    from kabot.agent.agent_scope import resolve_agent_workspace, resolve_agent_model

    # Setup config
    config = Config(
        agents=AgentsConfig(
            list=[
                AgentConfig(id="work", name="Work", model="openai/gpt-4o", workspace=str(tmp_path / "work")),
                AgentConfig(id="personal", name="Personal", model="anthropic/claude-sonnet-4-5", default=True)
            ],
            bindings=[
                AgentBinding(agent_id="work", channel="telegram"),
                AgentBinding(agent_id="personal", channel="whatsapp")
            ]
        )
    )

    # Test routing
    agent_id = resolve_agent_route(config, "telegram", "123")
    assert agent_id == "work"

    # Test session key
    session_key = build_agent_session_key(agent_id, "telegram", "123")
    assert session_key == "agent:work:telegram:123"

    # Test workspace resolution
    workspace = resolve_agent_workspace(config, agent_id)
    assert "work" in str(workspace)

    # Test model resolution
    model = resolve_agent_model(config, agent_id)
    assert model == "openai/gpt-4o"
```

**Step 2: Run test**

Run: `pytest tests/integration/test_multi_agent_flow.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_multi_agent_flow.py
git commit -m "test(integration): add multi-agent flow integration test

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Documentation

**Files:**
- Create: `docs/multi-agent.md`

**Step 1: Write documentation**

```markdown
# Multi-Agent System

Kabot supports multiple independent agents with separate contexts, models, and workspaces.

## Configuration

Add agents to `config.yaml`:

\`\`\`yaml
agents:
  list:
    - id: work
      name: Work Agent
      model: openai/gpt-4o
      workspace: ~/.kabot/workspace-work
      default: false

    - id: personal
      name: Personal Agent
      model: anthropic/claude-sonnet-4-5
      workspace: ~/.kabot/workspace-personal
      default: true

  bindings:
    - agent_id: work
      channel: telegram

    - agent_id: personal
      channel: whatsapp
\`\`\`

## CLI Commands

\`\`\`bash
# List agents
kabot agents list

# Add agent
kabot agents add work --name "Work Agent" --model openai/gpt-4o

# Delete agent
kabot agents delete work
\`\`\`

## Routing

Messages are routed to agents based on:
1. Exact channel + chat_id match
2. Channel-only match
3. Default agent (fallback)

## Session Isolation

Each agent has isolated:
- Workspace directory
- Session history
- Model configuration
```

**Step 2: Commit**

```bash
git add docs/multi-agent.md
git commit -m "docs: add multi-agent system documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Execution Complete

Phase 1 implementation provides:
- ✅ Multiple independent agents
- ✅ Per-agent model assignment
- ✅ Workspace isolation
- ✅ Message routing via bindings
- ✅ CLI management commands
- ✅ Full test coverage
- ✅ Documentation

**Next:** Phase 2 (Collaborative Orchestration) - see `2026-02-18-phase2-collaborative-orchestration.md`
