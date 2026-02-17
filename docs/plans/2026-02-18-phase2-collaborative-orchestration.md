# Phase 2: Collaborative Orchestration Implementation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement collaborative multi-agent orchestration where multiple agents work together on a single task with role-based specialization

**Architecture:** Role-based agents (Master, Brainstorming, Executor, Verifier) communicate peer-to-peer via MessageBus, coordinate tasks, and aggregate results

**Tech Stack:** Python 3.11+, asyncio, existing Kabot MessageBus/AgentLoop, role-based model assignment

**Prerequisites:** Phase 1 completed (OpenClaw-style multi-agent system)

---

## Task 10: Role Manager Schema

**Files:**
- Create: `kabot/agent/role_manager.py`
- Modify: `kabot/config/schema.py:70-90`
- Test: `tests/agent/test_role_manager.py`

**Step 1: Write failing test**

```python
# tests/agent/test_role_manager.py
def test_role_definitions():
    from kabot.agent.role_manager import AGENT_ROLES

    assert "master" in AGENT_ROLES
    assert "brainstorming" in AGENT_ROLES
    assert "executor" in AGENT_ROLES
    assert "verifier" in AGENT_ROLES

def test_get_role_config():
    from kabot.agent.role_manager import get_role_config

    config = get_role_config("master")
    assert config["default_model"] == "openai/gpt-4o"
    assert "planning" in config["capabilities"]
```

**Step 2: Run test**

Run: `pytest tests/agent/test_role_manager.py -v`
Expected: FAIL

**Step 3: Implement role manager**

```python
# kabot/agent/role_manager.py
AGENT_ROLES = {
    "master": {
        "description": "Coordinates tasks and makes high-level decisions",
        "default_model": "openai/gpt-4o",
        "capabilities": ["planning", "coordination", "decision_making"]
    },
    "brainstorming": {
        "description": "Generates creative ideas and explores approaches",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
        "capabilities": ["ideation", "analysis", "exploration"]
    },
    "executor": {
        "description": "Executes code and performs file operations",
        "default_model": "moonshot/kimi-k2.5",
        "capabilities": ["code_execution", "file_operations", "tool_usage"]
    },
    "verifier": {
        "description": "Reviews code and validates results",
        "default_model": "anthropic/claude-3-5-sonnet-20241022",
        "capabilities": ["code_review", "testing", "validation"]
    }
}

def get_role_config(role: str) -> dict:
    return AGENT_ROLES.get(role, {})

def list_roles() -> list[str]:
    return list(AGENT_ROLES.keys())
```

**Step 4: Run test**

Run: `pytest tests/agent/test_role_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/role_manager.py tests/agent/test_role_manager.py
git commit -m "feat(agent): implement role manager with predefined roles

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Agent Communication Protocol

**Files:**
- Create: `kabot/agent/agent_comm.py`
- Modify: `kabot/bus/queue.py:30-50`
- Test: `tests/agent/test_agent_comm.py`

**Step 1: Write failing test**

```python
# tests/agent/test_agent_comm.py
import pytest

@pytest.mark.asyncio
async def test_send_agent_message():
    from kabot.agent.agent_comm import AgentComm, AgentMessage
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    comm = AgentComm(bus, "agent-1")

    msg = await comm.send("agent-2", {"task": "analyze code"}, msg_type="request")
    assert msg.from_agent == "agent-1"
    assert msg.to_agent == "agent-2"
    assert msg.msg_type == "request"

@pytest.mark.asyncio
async def test_receive_agent_message():
    from kabot.agent.agent_comm import AgentComm
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    comm1 = AgentComm(bus, "agent-1")
    comm2 = AgentComm(bus, "agent-2")

    # Send message
    await comm1.send("agent-2", {"task": "test"})

    # Receive message
    msg = await comm2.receive(timeout=1.0)
    assert msg.from_agent == "agent-1"
    assert msg.content["task"] == "test"
```

**Step 2: Run test**

Run: `pytest tests/agent/test_agent_comm.py -v`
Expected: FAIL

**Step 3: Extend MessageBus**

```python
# kabot/bus/queue.py (add to __init__)
from dataclasses import dataclass

@dataclass
class AgentMessage:
    msg_id: str
    from_agent: str
    to_agent: str | None
    msg_type: str
    content: dict
    timestamp: float
    reply_to: str | None = None

class MessageBus:
    def __init__(self):
        # ... existing queues ...
        self.agent_messages: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self._agent_subscribers: dict[str, asyncio.Queue[AgentMessage]] = {}
```

**Step 4: Implement AgentComm**

```python
# kabot/agent/agent_comm.py
import asyncio
import uuid
from time import time
from kabot.bus.queue import MessageBus, AgentMessage

class AgentComm:
    def __init__(self, bus: MessageBus, agent_id: str):
        self.bus = bus
        self.agent_id = agent_id
        self._inbox: asyncio.Queue[AgentMessage] = asyncio.Queue()

        # Subscribe to messages for this agent
        if agent_id not in bus._agent_subscribers:
            bus._agent_subscribers[agent_id] = self._inbox

    async def send(
        self,
        to_agent: str,
        content: dict,
        msg_type: str = "request",
        reply_to: str | None = None
    ) -> AgentMessage:
        msg = AgentMessage(
            msg_id=str(uuid.uuid4())[:8],
            from_agent=self.agent_id,
            to_agent=to_agent,
            msg_type=msg_type,
            content=content,
            timestamp=time(),
            reply_to=reply_to
        )

        # Route to target agent's inbox
        if to_agent in self.bus._agent_subscribers:
            await self.bus._agent_subscribers[to_agent].put(msg)

        return msg

    async def receive(self, timeout: float = 10.0) -> AgentMessage:
        return await asyncio.wait_for(self._inbox.get(), timeout=timeout)

    async def broadcast(self, content: dict, msg_type: str = "broadcast") -> None:
        for agent_id, inbox in self.bus._agent_subscribers.items():
            if agent_id != self.agent_id:
                msg = AgentMessage(
                    msg_id=str(uuid.uuid4())[:8],
                    from_agent=self.agent_id,
                    to_agent=agent_id,
                    msg_type=msg_type,
                    content=content,
                    timestamp=time()
                )
                await inbox.put(msg)
```

**Step 5: Run test**

Run: `pytest tests/agent/test_agent_comm.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add kabot/agent/agent_comm.py kabot/bus/queue.py tests/agent/test_agent_comm.py
git commit -m "feat(agent): implement agent-to-agent communication protocol

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 12: Task Coordinator

**Files:**
- Create: `kabot/agent/coordinator.py`
- Test: `tests/agent/test_coordinator.py`

**Step 1: Write failing test**

```python
# tests/agent/test_coordinator.py
import pytest

@pytest.mark.asyncio
async def test_delegate_task():
    from kabot.agent.coordinator import Coordinator
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    coordinator = Coordinator(bus, "master-agent")

    task_id = await coordinator.delegate_task(
        task="Design authentication system",
        target_role="brainstorming"
    )

    assert task_id is not None
    assert task_id in coordinator._pending_tasks

@pytest.mark.asyncio
async def test_collect_results():
    from kabot.agent.coordinator import Coordinator
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    coordinator = Coordinator(bus, "master-agent")

    task_id = await coordinator.delegate_task("Test task", "executor")

    # Simulate result
    coordinator._task_results[task_id] = {"status": "completed", "output": "Done"}

    results = await coordinator.collect_results(task_id, timeout=0.1)
    assert results["status"] == "completed"
```

**Step 2: Run test**

Run: `pytest tests/agent/test_coordinator.py -v`
Expected: FAIL

**Step 3: Implement coordinator**

```python
# kabot/agent/coordinator.py
import asyncio
import uuid
from time import time
from kabot.bus.queue import MessageBus
from kabot.agent.agent_comm import AgentComm

class Coordinator:
    def __init__(self, bus: MessageBus, agent_id: str):
        self.bus = bus
        self.agent_id = agent_id
        self.comm = AgentComm(bus, agent_id)
        self._pending_tasks: dict[str, dict] = {}
        self._task_results: dict[str, dict] = {}

    async def delegate_task(
        self,
        task: str,
        target_role: str,
        context: dict | None = None
    ) -> str:
        task_id = str(uuid.uuid4())[:8]

        self._pending_tasks[task_id] = {
            "task": task,
            "role": target_role,
            "context": context or {},
            "created_at": time()
        }

        # Send task to role-specific agent
        await self.comm.send(
            to_agent=f"role:{target_role}",
            content={
                "task_id": task_id,
                "task": task,
                "context": context or {}
            },
            msg_type="task_delegation"
        )

        return task_id

    async def collect_results(
        self,
        task_id: str,
        timeout: float = 30.0
    ) -> dict:
        start_time = time()

        while time() - start_time < timeout:
            if task_id in self._task_results:
                result = self._task_results.pop(task_id)
                self._pending_tasks.pop(task_id, None)
                return result

            await asyncio.sleep(0.1)

        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    async def aggregate_results(self, results: list[dict]) -> dict:
        """Aggregate results from multiple agents."""
        return {
            "aggregated": True,
            "count": len(results),
            "results": results,
            "summary": self._summarize_results(results)
        }

    def _summarize_results(self, results: list[dict]) -> str:
        return f"Collected {len(results)} results"
```

**Step 4: Run test**

Run: `pytest tests/agent/test_coordinator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/coordinator.py tests/agent/test_coordinator.py
git commit -m "feat(agent): implement task coordinator for multi-agent collaboration

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 13: Mode Manager

**Files:**
- Create: `kabot/agent/mode_manager.py`
- Modify: `kabot/config/schema.py:90-110`
- Test: `tests/agent/test_mode_manager.py`

**Step 1: Write failing test**

```python
# tests/agent/test_mode_manager.py
def test_set_mode(tmp_path):
    from kabot.agent.mode_manager import ModeManager

    manager = ModeManager(tmp_path / "mode_config.json")
    manager.set_mode("user:telegram:123", "multi")

    mode = manager.get_mode("user:telegram:123")
    assert mode == "multi"

def test_default_mode(tmp_path):
    from kabot.agent.mode_manager import ModeManager

    manager = ModeManager(tmp_path / "mode_config.json")
    mode = manager.get_mode("user:telegram:999")
    assert mode == "single"  # default
```

**Step 2: Run test**

Run: `pytest tests/agent/test_mode_manager.py -v`
Expected: FAIL

**Step 3: Implement mode manager**

```python
# kabot/agent/mode_manager.py
import json
from pathlib import Path

class ModeManager:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self._save({"users": {}})

    def _load(self) -> dict:
        with open(self.config_path) as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def set_mode(self, user_id: str, mode: str) -> None:
        if mode not in ["single", "multi"]:
            raise ValueError(f"Invalid mode: {mode}")

        data = self._load()
        if user_id not in data["users"]:
            data["users"][user_id] = {}
        data["users"][user_id]["mode"] = mode
        self._save(data)

    def get_mode(self, user_id: str) -> str:
        data = self._load()
        return data["users"].get(user_id, {}).get("mode", "single")

    def set_custom_config(self, user_id: str, config: dict) -> None:
        data = self._load()
        if user_id not in data["users"]:
            data["users"][user_id] = {}
        data["users"][user_id]["custom_config"] = config
        self._save(data)

    def get_custom_config(self, user_id: str) -> dict:
        data = self._load()
        return data["users"].get(user_id, {}).get("custom_config", {})
```

**Step 4: Run test**

Run: `pytest tests/agent/test_mode_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/mode_manager.py tests/agent/test_mode_manager.py
git commit -m "feat(agent): implement mode manager for single/multi-agent selection

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 14: Mode Command

**Files:**
- Create: `kabot/cli/mode.py`
- Modify: `kabot/cli/commands.py:20-30`

**Step 1: Implement mode CLI**

```python
# kabot/cli/mode.py
import typer
from rich.console import Console

app = typer.Typer(help="Manage agent execution mode")
console = Console()

@app.command("set")
def set_mode(
    mode: str = typer.Argument(..., help="Mode: single or multi"),
    user_id: str = typer.Option("", help="User ID (default: current user)"),
):
    """Set agent execution mode."""
    from kabot.agent.mode_manager import ModeManager
    from pathlib import Path

    if mode not in ["single", "multi"]:
        console.print(f"[red]Invalid mode: {mode}. Use 'single' or 'multi'[/red]")
        raise typer.Exit(1)

    manager = ModeManager(Path.home() / ".kabot" / "mode_config.json")
    user_id = user_id or "default"
    manager.set_mode(user_id, mode)

    console.print(f"[green]✓[/green] Mode set to '{mode}' for {user_id}")

@app.command("status")
def show_status(
    user_id: str = typer.Option("", help="User ID (default: current user)"),
):
    """Show current mode."""
    from kabot.agent.mode_manager import ModeManager
    from pathlib import Path

    manager = ModeManager(Path.home() / ".kabot" / "mode_config.json")
    user_id = user_id or "default"
    mode = manager.get_mode(user_id)

    console.print(f"Current mode for {user_id}: [cyan]{mode}[/cyan]")
```

**Step 2: Register command**

```python
# kabot/cli/commands.py
from kabot.cli import mode

app.add_typer(mode.app, name="mode")
```

**Step 3: Test manually**

Run: `kabot mode set multi`
Expected: Mode set successfully

Run: `kabot mode status`
Expected: Shows "multi"

**Step 4: Commit**

```bash
git add kabot/cli/mode.py kabot/cli/commands.py
git commit -m "feat(cli): add mode command for single/multi-agent selection

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 15: Integration with AgentLoop

**Files:**
- Modify: `kabot/agent/loop.py:100-150`
- Test: `tests/agent/test_loop_collaborative.py`

**Step 1: Write failing test**

```python
# tests/agent/test_loop_collaborative.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_agent_loop_multi_mode(tmp_path):
    from kabot.agent.loop import AgentLoop
    from kabot.bus.queue import MessageBus
    from kabot.agent.mode_manager import ModeManager

    bus = MessageBus()
    provider = MagicMock()
    mode_manager = ModeManager(tmp_path / "mode_config.json")
    mode_manager.set_mode("user:telegram:123", "multi")

    loop = AgentLoop(bus, provider, tmp_path, mode_manager=mode_manager)

    # Should use collaborative mode
    assert loop.mode_manager.get_mode("user:telegram:123") == "multi"
```

**Step 2: Run test**

Run: `pytest tests/agent/test_loop_collaborative.py -v`
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
        mode_manager: ModeManager | None = None,
        # ... existing parameters ...
    ):
        from kabot.agent.mode_manager import ModeManager
        from kabot.agent.coordinator import Coordinator

        self.mode_manager = mode_manager or ModeManager(
            Path.home() / ".kabot" / "mode_config.json"
        )
        self.coordinator = Coordinator(bus, "master")
        # ... existing initialization ...

    async def _should_use_collaborative_mode(self, msg: InboundMessage) -> bool:
        user_id = f"user:{msg.channel}:{msg.chat_id}"
        mode = self.mode_manager.get_mode(user_id)
        return mode == "multi"

    async def _process_collaborative(self, msg: InboundMessage) -> OutboundMessage:
        """Process message using collaborative multi-agent mode."""
        # Delegate to brainstorming agent
        task_id = await self.coordinator.delegate_task(
            task=msg.content,
            target_role="brainstorming"
        )

        # Collect results
        result = await self.coordinator.collect_results(task_id)

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=result.get("output", "Task completed"),
            reply_to=msg.message_id
        )
```

**Step 4: Run test**

Run: `pytest tests/agent/test_loop_collaborative.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/agent/loop.py tests/agent/test_loop_collaborative.py
git commit -m "feat(agent): integrate collaborative mode into agent loop

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 16: Documentation

**Files:**
- Create: `docs/collaborative-orchestration.md`

**Step 1: Write documentation**

```markdown
# Collaborative Orchestration

Multiple agents work together on a single task with role-based specialization.

## Roles

- **Master**: Coordinates tasks and makes decisions
- **Brainstorming**: Generates ideas and explores approaches
- **Executor**: Executes code and performs operations
- **Verifier**: Reviews code and validates results

## Usage

Enable collaborative mode:

\`\`\`bash
kabot mode set multi
\`\`\`

Check current mode:

\`\`\`bash
kabot mode status
\`\`\`

## Example Workflow

\`\`\`
User: "Implement user authentication"
  ↓
Master Agent: Analyzes request
  ↓
Brainstorming Agent: Proposes 3 approaches
  ↓
Master Agent: Selects JWT approach
  ↓
Executor Agent: Implements code
  ↓
Verifier Agent: Reviews implementation
  ↓
Master Agent: Aggregates results → User
\`\`\`

## Configuration

Custom role-model assignment in `config.yaml`:

\`\`\`yaml
collaborative:
  roles:
    master: openai/gpt-4o
    brainstorming: anthropic/claude-3-5-sonnet-20241022
    executor: moonshot/kimi-k2.5
    verifier: anthropic/claude-3-5-sonnet-20241022
\`\`\`
```

**Step 2: Commit**

```bash
git add docs/collaborative-orchestration.md
git commit -m "docs: add collaborative orchestration documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Execution Complete

Phase 2 implementation provides:
- ✅ Role-based agent system (Master, Brainstorming, Executor, Verifier)
- ✅ Agent-to-agent communication protocol
- ✅ Task coordination and delegation
- ✅ Result aggregation
- ✅ Mode selection (single vs multi)
- ✅ CLI commands for mode management
- ✅ Integration with AgentLoop
- ✅ Full documentation

**Combined System:** Both Phase 1 (OpenClaw-style) and Phase 2 (Collaborative) work together without conflicts.
