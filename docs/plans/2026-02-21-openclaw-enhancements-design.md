# OpenClaw-Inspired Enhancement Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Adapt 6 key features from OpenClaw into Kabot for safety, automation, and interactive UX.

**Architecture:** Inside-Out approach — Phase 2 (safety), Phase 3 (cron delivery), Phase 4 (interactive UI), Phase 5 (sandbox). Each phase is independently deployable. All changes use existing Pydantic schema patterns and pytest class-based testing.

**Tech Stack:** Python 3.11+, Pydantic, pytest, python-telegram-bot, discord.py REST API, aiohttp, Docker SDK (optional)

---

## Task 1: Sub-agent Depth Control — Config Schema

**Files:**
- Modify: `kabot/config/schema.py:140-186`
- Test: `tests/config/test_subagent_config.py`

**Step 1: Write failing test**

```python
"""Tests for SubagentConfig schema."""
import pytest
from kabot.config.schema import SubagentDefaults, AgentDefaults


class TestSubagentDefaults:
    def test_defaults(self):
        cfg = SubagentDefaults()
        assert cfg.max_spawn_depth == 1
        assert cfg.max_children_per_agent == 5
        assert cfg.archive_after_minutes == 60

    def test_custom_values(self):
        cfg = SubagentDefaults(max_spawn_depth=3, max_children_per_agent=10)
        assert cfg.max_spawn_depth == 3
        assert cfg.max_children_per_agent == 10

    def test_agent_defaults_has_subagents(self):
        defaults = AgentDefaults()
        assert hasattr(defaults, 'subagents')
        assert isinstance(defaults.subagents, SubagentDefaults)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/config/test_subagent_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'SubagentDefaults'`

**Step 3: Write implementation**

Add to `kabot/config/schema.py` before `AgentDefaults` (around line 140):

```python
class SubagentDefaults(BaseModel):
    """Sub-agent safety limits."""
    max_spawn_depth: int = 1        # 1 = no nested spawning
    max_children_per_agent: int = 5  # Max concurrent subagents per parent
    archive_after_minutes: int = 60  # Auto-cleanup completed runs
```

Add field to `AgentDefaults`:

```python
    subagents: SubagentDefaults = Field(default_factory=SubagentDefaults)
```

**Step 4: Run test**

Run: `pytest tests/config/test_subagent_config.py -v`
Expected: PASS (3 passed)

**Step 5: Commit**

```bash
git add kabot/config/schema.py tests/config/test_subagent_config.py
git commit -m "feat(config): add SubagentDefaults schema with depth/children/archive limits"
```

---

## Task 2: Enforce Sub-agent Limits in SubagentManager

**Files:**
- Modify: `kabot/agent/subagent.py:32-112`
- Test: `tests/agent/test_subagent_limits.py`

**Step 1: Write failing test**

```python
"""Tests for sub-agent spawn limits."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from kabot.agent.subagent import SubagentManager
from kabot.config.schema import SubagentDefaults


@pytest.fixture
def mock_provider():
    p = MagicMock()
    p.get_default_model.return_value = "test/model"
    return p


@pytest.fixture
def mock_bus():
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    return bus


@pytest.fixture
def manager(mock_provider, mock_bus, tmp_path):
    return SubagentManager(
        provider=mock_provider,
        workspace=tmp_path,
        bus=mock_bus,
        subagent_config=SubagentDefaults(max_children_per_agent=2),
    )


class TestSubagentLimits:
    @pytest.mark.asyncio
    async def test_rejects_when_max_children_reached(self, manager):
        """spawn() should reject if running count >= max_children_per_agent."""
        manager._running_tasks = {"a": MagicMock(), "b": MagicMock()}
        result = await manager.spawn("task3")
        assert "limit" in result.lower() or "max" in result.lower()

    @pytest.mark.asyncio
    async def test_allows_spawn_under_limit(self, manager):
        """spawn() should allow if running count < max_children_per_agent."""
        with patch.object(manager, '_run_subagent', new_callable=AsyncMock):
            result = await manager.spawn("task1")
            assert "started" in result.lower()

    def test_default_depth_is_tracked(self, manager):
        """Manager should track current_depth."""
        assert manager.current_depth == 0

    @pytest.mark.asyncio
    async def test_rejects_nested_spawn_at_max_depth(self, manager):
        """spawn() should reject when depth >= max_spawn_depth."""
        manager.current_depth = 1  # At max (default max_spawn_depth=1)
        result = await manager.spawn("nested task")
        assert "depth" in result.lower() or "nested" in result.lower()
```

**Step 2: Run test**

Run: `pytest tests/agent/test_subagent_limits.py -v`
Expected: FAIL — `TypeError: __init__() got unexpected keyword argument 'subagent_config'`

**Step 3: Implement**

Update `SubagentManager.__init__` to accept and store `subagent_config`:

```python
def __init__(
    self,
    provider: LLMProvider,
    workspace: Path,
    bus: MessageBus,
    model: str | None = None,
    brave_api_key: str | None = None,
    exec_config: "ExecToolConfig | None" = None,
    restrict_to_workspace: bool = False,
    http_guard: Any | None = None,
    meta_config: Any | None = None,
    subagent_config: "SubagentDefaults | None" = None,
):
    from kabot.config.schema import ExecToolConfig, SubagentDefaults
    self.provider = provider
    self.workspace = workspace
    self.bus = bus
    self.model = model or provider.get_default_model()
    self.brave_api_key = brave_api_key
    self.exec_config = exec_config or ExecToolConfig()
    self.restrict_to_workspace = restrict_to_workspace
    self.http_guard = http_guard
    self.meta_config = meta_config
    self.subagent_config = subagent_config or SubagentDefaults()
    self.current_depth: int = 0
    self._running_tasks: dict[str, asyncio.Task[None]] = {}

    registry_path = Path.home() / ".kabot" / "subagents" / "runs.json"
    self.registry = SubagentRegistry(registry_path)
    self.registry.cleanup_old_runs(
        max_age_seconds=self.subagent_config.archive_after_minutes * 60
    )
```

Add guards in `spawn()`:

```python
async def spawn(self, task, label=None, origin_channel="cli",
                origin_chat_id="direct", parent_session_key="unknown"):
    # Guard: max children
    if self.get_running_count() >= self.subagent_config.max_children_per_agent:
        return (f"Cannot spawn: limit of {self.subagent_config.max_children_per_agent} "
                f"concurrent subagents reached. Wait for a running task to complete.")

    # Guard: max depth
    if self.current_depth >= self.subagent_config.max_spawn_depth:
        return (f"Cannot spawn: maximum nesting depth of "
                f"{self.subagent_config.max_spawn_depth} reached. "
                f"Nested sub-agent spawning is not allowed at this depth.")

    # ... existing spawn logic unchanged ...
```

**Step 4: Run test**

Run: `pytest tests/agent/test_subagent_limits.py -v`
Expected: PASS (4 passed)

**Step 5: Commit**

```bash
git add kabot/agent/subagent.py tests/agent/test_subagent_limits.py
git commit -m "feat(subagent): enforce maxSpawnDepth and maxChildrenPerAgent limits"
```

---

## Task 3: Heartbeat Config & Delivery Target

**Files:**
- Modify: `kabot/config/schema.py`
- Modify: `kabot/heartbeat/service.py`
- Test: `tests/heartbeat/test_heartbeat_config.py`

**Step 1: Write failing test**

```python
"""Tests for HeartbeatConfig and active-hours filtering."""
import pytest
from datetime import time as dtime
from kabot.config.schema import HeartbeatDefaults


class TestHeartbeatDefaults:
    def test_defaults(self):
        cfg = HeartbeatDefaults()
        assert cfg.enabled is True
        assert cfg.interval_minutes == 30
        assert cfg.target_channel == "last"
        assert cfg.target_to == ""
        assert cfg.active_hours_start == ""
        assert cfg.active_hours_end == ""

    def test_custom(self):
        cfg = HeartbeatDefaults(
            interval_minutes=15,
            target_channel="telegram",
            target_to="123456",
            active_hours_start="08:00",
            active_hours_end="22:00",
        )
        assert cfg.interval_minutes == 15
        assert cfg.target_channel == "telegram"


class TestHeartbeatActiveHours:
    def test_is_within_active_hours_no_config(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("", "") is True

    def test_is_within_active_hours_inside(self):
        from kabot.heartbeat.service import is_within_active_hours
        result = is_within_active_hours("00:00", "23:59", test_hour=12)
        assert result is True

    def test_is_within_active_hours_outside(self):
        from kabot.heartbeat.service import is_within_active_hours
        result = is_within_active_hours("09:00", "17:00", test_hour=3)
        assert result is False
```

**Step 2: Run test** → FAIL (import errors)

**Step 3: Implement**

Add to `schema.py`:

```python
class HeartbeatDefaults(BaseModel):
    """Heartbeat delivery and scheduling configuration."""
    enabled: bool = True
    interval_minutes: int = 30
    target_channel: str = "last"  # "last", "none", or channel name
    target_to: str = ""           # Chat ID / phone number
    active_hours_start: str = ""  # "08:00" (24h), empty = always
    active_hours_end: str = ""    # "22:00"
```

Add `is_within_active_hours()` to `heartbeat/service.py`:

```python
def is_within_active_hours(start: str, end: str, *, test_hour: int | None = None) -> bool:
    if not start or not end:
        return True
    from datetime import datetime
    now_h = test_hour if test_hour is not None else datetime.now().hour
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    now_min = now_h * 60
    if start_min <= end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min
```

Update `HeartbeatService._loop()` to use `is_within_active_hours()`.

**Step 4:** `pytest tests/heartbeat/test_heartbeat_config.py -v` → PASS

**Step 5: Commit**

```bash
git add kabot/config/schema.py kabot/heartbeat/service.py tests/heartbeat/test_heartbeat_config.py
git commit -m "feat(heartbeat): add HeartbeatDefaults config with active-hours and delivery target"
```

---

## Task 4: Cron Webhook Delivery Modes

**Files:**
- Modify: `kabot/cron/types.py`
- Modify: `kabot/cron/delivery.py`
- Modify: `kabot/cron/service.py`
- Test: `tests/cron/test_cron_delivery_modes.py`

**Step 1: Write failing test**

```python
"""Tests for cron delivery modes (announce/webhook/none)."""
import pytest
from kabot.cron.delivery import resolve_delivery_plan
from kabot.cron.types import CronJob, CronPayload, CronDeliveryConfig, CronSchedule


class TestResolveDeliveryPlan:
    def test_announce_mode(self):
        job = CronJob(id="j1", name="test",
                      schedule=CronSchedule(kind="every"),
                      payload=CronPayload(message="hi"),
                      delivery=CronDeliveryConfig(mode="announce", channel="telegram", to="123"))
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "announce"
        assert plan["channel"] == "telegram"

    def test_webhook_mode(self):
        job = CronJob(id="j2", name="test",
                      schedule=CronSchedule(kind="every"),
                      payload=CronPayload(message="hi"),
                      delivery=CronDeliveryConfig(mode="webhook", webhook_url="https://example.com/hook"))
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "webhook"
        assert plan["webhook_url"] == "https://example.com/hook"

    def test_none_mode(self):
        job = CronJob(id="j3", name="test",
                      schedule=CronSchedule(kind="every"),
                      payload=CronPayload(message="hi"),
                      delivery=CronDeliveryConfig(mode="none"))
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "none"

    def test_legacy_deliver_true(self):
        """Jobs without delivery config but deliver=True → announce."""
        job = CronJob(id="j4", name="test",
                      schedule=CronSchedule(kind="every"),
                      payload=CronPayload(message="hi", deliver=True, channel="telegram", to="123"))
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "announce"

    def test_legacy_deliver_false(self):
        """Jobs with deliver=False → none."""
        job = CronJob(id="j5", name="test",
                      schedule=CronSchedule(kind="every"),
                      payload=CronPayload(message="hi", deliver=False))
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "none"
```

**Step 2:** `pytest tests/cron/test_cron_delivery_modes.py -v` → FAIL

**Step 3: Implement**

Add to `cron/types.py`:

```python
@dataclass
class CronDeliveryConfig:
    """Delivery configuration for a cron job."""
    mode: Literal["announce", "webhook", "none"] = "announce"
    channel: str = "last"
    to: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""
```

Add `delivery` field to `CronJob`:

```python
    delivery: CronDeliveryConfig | None = None
```

Rewrite `cron/delivery.py`:

```python
"""Cron delivery plan resolver."""
from kabot.cron.types import CronJob


def resolve_delivery_plan(job: CronJob) -> dict:
    if job.delivery:
        d = job.delivery
        return {
            "mode": d.mode,
            "channel": d.channel if d.mode == "announce" else None,
            "to": d.to or None,
            "webhook_url": d.webhook_url if d.mode == "webhook" else None,
        }
    # Legacy fallback
    p = job.payload
    if p.deliver:
        return {"mode": "announce", "channel": p.channel or "last", "to": p.to}
    return {"mode": "none", "channel": None, "to": None}


def infer_delivery(session_key: str) -> dict | None:
    """Legacy: Auto-detect channel and recipient from session key."""
    if not session_key or session_key.startswith("background:"):
        return None
    parts = session_key.split(":", 1)
    if len(parts) < 2:
        return None
    channel, to = parts[0].strip(), parts[1].strip()
    if not channel or not to:
        return None
    return {"channel": channel, "to": to}
```

**Step 4:** `pytest tests/cron/test_cron_delivery_modes.py -v` → PASS

**Step 5: Commit**

```bash
git add kabot/cron/types.py kabot/cron/delivery.py tests/cron/test_cron_delivery_modes.py
git commit -m "feat(cron): add announce/webhook/none delivery modes"
```

---

## Task 5: Cron Webhook POST Execution

**Files:**
- Modify: `kabot/cron/service.py`
- Test: `tests/cron/test_cron_webhook_post.py`

**Step 1: Write failing test**

```python
"""Tests for cron webhook POST delivery."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from kabot.cron.service import _deliver_webhook


class TestWebhookPost:
    @pytest.mark.asyncio
    async def test_webhook_post_success(self):
        with patch("kabot.cron.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client
            result = await _deliver_webhook(
                url="https://example.com/hook",
                job_id="j1",
                job_name="Test",
                output="Hello",
                secret="mysecret",
            )
            assert result is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_webhook_post_hmac_header(self):
        with patch("kabot.cron.service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_cls.return_value = mock_client
            await _deliver_webhook("https://x.com/h", "j1", "t", "o", secret="sec")
            call_kwargs = mock_client.post.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "X-Kabot-Signature" in headers
```

**Step 2:** FAIL

**Step 3: Implement** — add `_deliver_webhook()` async function to `cron/service.py`:

```python
import hashlib, hmac, httpx, json as _json

async def _deliver_webhook(url: str, job_id: str, job_name: str,
                           output: str, secret: str = "") -> bool:
    body = _json.dumps({"job_id": job_id, "job_name": job_name, "output": output})
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Kabot-Signature"] = f"sha256={sig}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, content=body, headers=headers)
        return 200 <= resp.status_code < 300
```

**Step 4:** PASS

**Step 5: Commit**

```bash
git add kabot/cron/service.py tests/cron/test_cron_webhook_post.py
git commit -m "feat(cron): add webhook POST delivery with HMAC signature"
```

---

## Task 6: Telegram Inline Buttons

**Files:**
- Modify: `kabot/channels/telegram.py`
- Test: `tests/channels/test_telegram_buttons.py`

**Step 1: Write failing test**

```python
"""Tests for Telegram inline button support."""
import pytest
from kabot.channels.telegram import build_inline_keyboard


class TestBuildInlineKeyboard:
    def test_single_row(self):
        buttons = [{"text": "Yes", "callback_data": "yes"},
                   {"text": "No", "callback_data": "no"}]
        markup = build_inline_keyboard([buttons])
        assert markup is not None
        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 2

    def test_multiple_rows(self):
        rows = [
            [{"text": "A", "callback_data": "a"}],
            [{"text": "B", "callback_data": "b"}],
        ]
        markup = build_inline_keyboard(rows)
        assert len(markup.inline_keyboard) == 2

    def test_url_button(self):
        buttons = [{"text": "Visit", "url": "https://example.com"}]
        markup = build_inline_keyboard([buttons])
        assert markup.inline_keyboard[0][0].url == "https://example.com"

    def test_empty_returns_none(self):
        assert build_inline_keyboard([]) is None
```

**Step 2:** FAIL

**Step 3: Implement** — add `build_inline_keyboard()` to `channels/telegram.py`:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def build_inline_keyboard(rows: list[list[dict]]) -> InlineKeyboardMarkup | None:
    if not rows:
        return None
    keyboard = []
    for row in rows:
        kb_row = []
        for btn in row:
            if "url" in btn:
                kb_row.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
            else:
                kb_row.append(InlineKeyboardButton(
                    text=btn["text"],
                    callback_data=btn.get("callback_data", btn["text"]),
                ))
        keyboard.append(kb_row)
    return InlineKeyboardMarkup(keyboard)
```

Add callback handler in `TelegramChannel.start()` and wire to bus.

**Step 4:** PASS

**Step 5: Commit**

```bash
git add kabot/channels/telegram.py tests/channels/test_telegram_buttons.py
git commit -m "feat(telegram): add inline keyboard button support"
```

---

## Task 7: Telegram Callback Query Handler

**Files:**
- Modify: `kabot/channels/telegram.py`
- Test: `tests/channels/test_telegram_callback.py`

**Step 1: Write failing test** — test that callback queries produce `InboundMessage` on bus

**Step 2:** FAIL

**Step 3: Implement** — add `_on_callback_query()` handler, register `CallbackQueryHandler` in `start()`

**Step 4:** PASS

**Step 5: Commit**

```bash
git commit -m "feat(telegram): handle callback query events from inline buttons"
```

---

## Task 8: Discord Interactive Components (Buttons)

**Files:**
- Create: `kabot/channels/discord_components.py`
- Modify: `kabot/channels/discord.py`
- Test: `tests/channels/test_discord_components.py`

**Step 1: Write failing test**

```python
"""Tests for Discord component builder."""
import pytest
from kabot.channels.discord_components import build_action_row, ButtonStyle


class TestDiscordComponents:
    def test_build_action_row_buttons(self):
        row = build_action_row(buttons=[
            {"label": "Approve", "style": ButtonStyle.SUCCESS, "custom_id": "approve"},
            {"label": "Reject", "style": ButtonStyle.DANGER, "custom_id": "reject"},
        ])
        assert row["type"] == 1  # ACTION_ROW
        assert len(row["components"]) == 2
        assert row["components"][0]["label"] == "Approve"

    def test_button_style_mapping(self):
        assert ButtonStyle.PRIMARY == 1
        assert ButtonStyle.DANGER == 4

    def test_url_button(self):
        row = build_action_row(buttons=[
            {"label": "Visit", "style": ButtonStyle.LINK, "url": "https://example.com"},
        ])
        assert row["components"][0]["url"] == "https://example.com"
```

**Step 2:** FAIL

**Step 3: Implement** `discord_components.py`:

```python
"""Discord component builders for interactive messages."""
from enum import IntEnum


class ButtonStyle(IntEnum):
    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5


def build_action_row(buttons: list[dict]) -> dict:
    components = []
    for btn in buttons:
        comp = {"type": 2, "label": btn["label"], "style": btn["style"]}
        if btn["style"] == ButtonStyle.LINK:
            comp["url"] = btn["url"]
        else:
            comp["custom_id"] = btn.get("custom_id", btn["label"].lower())
        components.append(comp)
    return {"type": 1, "components": components}
```

**Step 4:** PASS

**Step 5: Commit**

```bash
git add kabot/channels/discord_components.py tests/channels/test_discord_components.py
git commit -m "feat(discord): add interactive component builder (buttons, action rows)"
```

---

## Task 9: Discord Interaction Handler

**Files:**
- Modify: `kabot/channels/discord.py`
- Test: `tests/channels/test_discord_interaction.py`

Handle `INTERACTION_CREATE` opcode in gateway loop, wire to MessageBus.

**Step 1-5:** Similar TDD flow as Task 7.

```bash
git commit -m "feat(discord): handle INTERACTION_CREATE for button clicks"
```

---

## Task 10: Docker Sandbox Module

**Files:**
- Create: `kabot/sandbox/__init__.py`
- Create: `kabot/sandbox/docker_sandbox.py`
- Create: `Dockerfile.sandbox`
- Test: `tests/sandbox/test_docker_sandbox.py`

**Step 1: Write failing test**

```python
"""Tests for Docker sandbox (mocked Docker SDK)."""
import pytest
from unittest.mock import MagicMock, patch
from kabot.sandbox.docker_sandbox import DockerSandbox


class TestDockerSandbox:
    def test_init_sets_defaults(self):
        sb = DockerSandbox(image="kabot-sandbox")
        assert sb.image == "kabot-sandbox"
        assert sb.workspace_access == "rw"

    @pytest.mark.asyncio
    async def test_exec_command_returns_output(self):
        with patch("kabot.sandbox.docker_sandbox.docker") as mock_docker:
            mock_container = MagicMock()
            mock_container.exec_run.return_value = (0, b"hello\n")
            mock_docker.from_env.return_value.containers.run.return_value = mock_container
            sb = DockerSandbox(image="test")
            result = await sb.exec_command("echo hello")
            assert "hello" in result

    def test_sandbox_off_is_noop(self):
        sb = DockerSandbox(image="test", mode="off")
        assert sb.is_active is False
```

**Step 2-5:** Standard TDD flow.

**Dockerfile.sandbox:**

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl git jq ripgrep && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash sandbox
USER sandbox
WORKDIR /home/sandbox
CMD ["sleep", "infinity"]
```

```bash
git add kabot/sandbox/ Dockerfile.sandbox tests/sandbox/
git commit -m "feat(sandbox): add Docker sandbox module with exec isolation"
```

---

## Task 11: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Prepend new section under `## [Unreleased]`:**

```markdown
### Added - OpenClaw-Inspired Enhancements (2026-02-21)

- **Sub-agent Safety Limits:**
  - Added `SubagentDefaults` config with `max_spawn_depth`, `max_children_per_agent`, `archive_after_minutes`.
  - `SubagentManager.spawn()` now enforces max-children and nested-depth limits.
  - Auto-archive completed subagent runs based on configurable timeout.
- **Heartbeat Delivery & Active Hours:**
  - Added `HeartbeatDefaults` config with `target_channel`, `target_to`, `active_hours_start/end`.
  - Heartbeat now skips execution outside configured active-hours window.
  - Heartbeat results can be routed to specific channel/chat ID.
- **Cron Webhook Delivery Modes:**
  - Added `CronDeliveryConfig` with 3 modes: `announce` (chat), `webhook` (HTTP POST), `none` (silent).
  - Webhook delivery includes HMAC-SHA256 signature via `X-Kabot-Signature` header.
  - Backward-compatible with legacy `deliver: true/false` payload format.
- **Telegram Inline Buttons:**
  - Added `build_inline_keyboard()` for creating InlineKeyboardMarkup from button specs.
  - Added `CallbackQueryHandler` to handle button click events.
  - Button clicks are wired to agent via MessageBus as `InboundMessage`.
- **Discord Interactive Components:**
  - Added `discord_components.py` with `build_action_row()` and `ButtonStyle` enum.
  - Discord channel now handles `INTERACTION_CREATE` for button/select interactions.
  - Components are sent via REST API message payload.
- **Docker Sandbox Execution (Optional):**
  - Added `kabot/sandbox/` module with `DockerSandbox` class for isolated command execution.
  - Added `Dockerfile.sandbox` (Python 3.11 slim + common tools).
  - Sandbox supports `off`, `non-main`, and `all` modes via config.
```

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG with OpenClaw-inspired enhancements"
```

---

## Task 12: Final Integration Test

**Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All existing tests + new tests pass. No regressions.

**Step 2: Final commit**

```bash
git add -A
git commit -m "chore: final integration verification for OpenClaw enhancements"
```
