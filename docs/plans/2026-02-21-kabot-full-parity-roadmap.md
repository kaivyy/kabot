# Kabot Full-Parity Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all 10 verified gaps between Kabot and OpenClaw, transforming Kabot from a capable chatbot into a production-grade autonomous agent platform.

**Architecture:** Layered inside-out approach — start with backend safety (sub-agent limits, security hardening), then automation (cron delivery, heartbeat), then interactive UX (Telegram/Discord buttons), then infrastructure (sandbox, daemon audit). Each task is independently deployable and tested. Config changes go into `schema.py` using existing Pydantic patterns. All new modules get pytest coverage.

**Tech Stack:** Python 3.11+, Pydantic, pytest, python-telegram-bot (InlineKeyboardMarkup), Discord REST API v10, httpx (webhook POST), aiohttp (gateway), Docker SDK (optional)

**Verified Gap Counts (from source audit):**

| Area | Kabot Files | OpenClaw Files |
|---|---|---|
| Gateway | 5 | 171 |
| Security | 1 | 24 |
| Plugins | 6 | 53 |
| Hooks | 1 | 27 |
| Daemon | autostart | 38 |
| Memory | 3 | 81 |
| Browser | 1 | 93 |
| TUI | wizard | 27 |
| Channels | 8 | 8 + iMessage(15) + Line(42) + Signal(26) |

---

## Post-Implementation Verification (2026-02-21)

This section captures the verified repository state after running a direct code-and-test audit against this plan.

### Overall Status

- Completed: Task 1, 2, 3, 4, 5, 6, 7, 9
- Partial: Task 8, 10, 12
- Missing: Task 11
- Not yet green: Task 13 (full test suite still failing)

### Task Status Snapshot

| Task | Status | Evidence (Kabot) | Notes |
|---|---|---|---|
| 1 | Done | `kabot/config/schema.py`, `tests/config/test_subagent_config.py` | `SubagentDefaults` implemented and tested. |
| 2 | Done | `kabot/agent/subagent.py`, `tests/agent/test_subagent_limits.py` | Spawn depth and children guards present. |
| 3 | Done | `kabot/heartbeat/service.py`, `tests/heartbeat/test_heartbeat_config.py` | Active-hours logic exists; test filename differs from plan. |
| 4 | Done | `kabot/cron/types.py`, `kabot/cron/delivery.py`, `tests/cron/test_cron_delivery_modes.py` | Delivery mode resolver implemented. |
| 5 | Done | `kabot/cron/service.py`, `tests/cron/test_cron_webhook_post.py` | Webhook POST and `X-Kabot-Signature` covered. |
| 6 | Done | `kabot/channels/telegram.py`, `tests/channels/test_telegram_buttons.py` | Inline keyboard builder implemented; test filename differs from plan. |
| 7 | Done | `kabot/channels/telegram.py`, `tests/channels/test_telegram_callback.py` | Callback query handler implemented; test filename differs from plan. |
| 8 | Partial | `kabot/channels/discord_components.py`, `tests/channels/test_discord_components.py` | `build_action_row()` exists, but `build_select_menu()` from plan is absent. |
| 9 | Done | `kabot/channels/discord.py`, `tests/channels/test_discord_interaction.py` | Interaction handling implemented; test filename differs from plan. |
| 10 | Partial | `kabot/sandbox/docker_sandbox.py`, `tests/sandbox/test_docker_sandbox.py`, `Dockerfile.sandbox` | Module exists but behavior differs from plan (default mode/return semantics). |
| 11 | Missing | _Not found:_ `kabot/security/audit_trail.py`, `tests/security/test_audit_trail.py` | Planned audit trail logger not implemented. |
| 12 | Partial | `CHANGELOG.md` | Changelog section exists but heading/content differs from this plan text. |
| 13 | Failing | `pytest tests/ -q` | Full suite result: `757 passed, 9 failed, 6 skipped` (firewall tests). |

### Verification Commands Executed

```bash
pytest tests/config/test_subagent_config.py tests/agent/test_subagent_limits.py tests/heartbeat/test_heartbeat_config.py tests/cron/test_cron_delivery_modes.py tests/cron/test_cron_webhook_post.py tests/channels/test_telegram_buttons.py tests/channels/test_telegram_callback.py tests/channels/test_discord_components.py tests/channels/test_discord_interaction.py tests/sandbox/test_docker_sandbox.py -q
```

Result: `31 passed`

```bash
pytest tests/ -q
```

Result: `757 passed, 9 failed, 6 skipped`

### Detailed Evidence Report

For full evidence mapping (including OpenClaw reference locations), see:
`docs/openclaw-analysis/2026-02-21-kabot-full-parity-verification.md`

---

## Task 1: Sub-agent Safety Limits Config

**Files:**
- Modify: `kabot/config/schema.py:140-147`
- Create: `tests/config/test_subagent_config.py`

**Step 1: Write the failing test**

```python
"""Tests for SubagentDefaults config schema."""
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

    def test_agent_defaults_includes_subagents(self):
        defaults = AgentDefaults()
        assert hasattr(defaults, "subagent_defaults")
        assert isinstance(defaults.subagent_defaults, SubagentDefaults)

    def test_zero_depth_blocks_all_spawning(self):
        cfg = SubagentDefaults(max_spawn_depth=0)
        assert cfg.max_spawn_depth == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/config/test_subagent_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'SubagentDefaults'`

**Step 3: Write minimal implementation**

Add to `kabot/config/schema.py` before `class AgentDefaults` (line ~140):

```python
class SubagentDefaults(BaseModel):
    """Sub-agent safety and lifecycle limits."""
    max_spawn_depth: int = 1        # 1 = flat only, no nested spawning
    max_children_per_agent: int = 5  # Max concurrent subagents per parent
    archive_after_minutes: int = 60  # Auto-cleanup completed runs
```

Add field to `AgentDefaults`:

```python
    subagent_defaults: SubagentDefaults = Field(default_factory=SubagentDefaults)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/config/test_subagent_config.py -v`
Expected: PASS (4 passed)

**Step 5: Commit**

```bash
git add kabot/config/schema.py tests/config/test_subagent_config.py
git commit -m "feat(config): add SubagentDefaults with max_spawn_depth and max_children limits"
```

---

## Task 2: Enforce Sub-agent Spawn Guards

**Files:**
- Modify: `kabot/agent/subagent.py:32-112`
- Create: `tests/agent/test_subagent_limits.py`

**Step 1: Write the failing test**

```python
"""Tests for sub-agent spawn limit enforcement."""
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
        subagent_config=SubagentDefaults(max_children_per_agent=2, max_spawn_depth=1),
    )


class TestSubagentSpawnGuards:
    @pytest.mark.asyncio
    async def test_rejects_when_max_children_reached(self, manager):
        """spawn() rejects if running_count >= max_children_per_agent."""
        manager._running_tasks = {"a": MagicMock(), "b": MagicMock()}
        result = await manager.spawn("task3")
        assert "limit" in result.lower() or "max" in result.lower()

    @pytest.mark.asyncio
    async def test_allows_spawn_under_limit(self, manager):
        """spawn() allows if running_count < max_children_per_agent."""
        with patch.object(manager, "_run_subagent", new_callable=AsyncMock):
            result = await manager.spawn("task1")
            assert "started" in result.lower()

    @pytest.mark.asyncio
    async def test_rejects_at_max_depth(self, manager):
        """spawn() rejects when depth >= max_spawn_depth."""
        manager.current_depth = 1
        result = await manager.spawn("nested task")
        assert "depth" in result.lower()

    def test_current_depth_starts_at_zero(self, manager):
        assert manager.current_depth == 0

    @pytest.mark.asyncio
    async def test_archive_uses_config_minutes(self, manager):
        """Registry cleanup uses archive_after_minutes from config."""
        # Verify that cleanup was called with correct seconds
        assert manager.subagent_config.archive_after_minutes == 60
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/agent/test_subagent_limits.py -v`
Expected: FAIL — `TypeError: __init__() got unexpected keyword argument 'subagent_config'`

**Step 3: Write minimal implementation**

Update `SubagentManager.__init__` signature to accept `subagent_config`:

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

Add guards at the top of `spawn()`:

```python
async def spawn(self, task, label=None, origin_channel="cli",
                origin_chat_id="direct", parent_session_key="unknown"):
    # Guard: max children
    if self.get_running_count() >= self.subagent_config.max_children_per_agent:
        return (f"Cannot spawn subagent: limit of "
                f"{self.subagent_config.max_children_per_agent} "
                f"concurrent subagents reached. Wait for a running task to finish.")

    # Guard: max depth
    if self.current_depth >= self.subagent_config.max_spawn_depth:
        return (f"Cannot spawn subagent: maximum nesting depth of "
                f"{self.subagent_config.max_spawn_depth} reached.")

    # ... rest of existing spawn logic unchanged ...
```

**Step 4: Run test**

Run: `pytest tests/agent/test_subagent_limits.py -v`
Expected: PASS (5 passed)

**Step 5: Commit**

```bash
git add kabot/agent/subagent.py tests/agent/test_subagent_limits.py
git commit -m "feat(subagent): enforce max_children and max_spawn_depth guards"
```

---

## Task 3: Heartbeat Delivery & Active-Hours Config

**Files:**
- Modify: `kabot/config/schema.py`
- Modify: `kabot/heartbeat/service.py`
- Create: `tests/heartbeat/test_heartbeat_delivery.py`

**Step 1: Write the failing test**

```python
"""Tests for HeartbeatDefaults config and active-hours logic."""
import pytest
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

    def test_custom_values(self):
        cfg = HeartbeatDefaults(
            interval_minutes=15,
            target_channel="telegram",
            target_to="123456",
            active_hours_start="08:00",
            active_hours_end="22:00",
        )
        assert cfg.target_channel == "telegram"
        assert cfg.active_hours_start == "08:00"


class TestActiveHoursCheck:
    def test_no_config_always_active(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("", "") is True

    def test_inside_window(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("08:00", "22:00", test_hour=12) is True

    def test_outside_window(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("09:00", "17:00", test_hour=3) is False

    def test_overnight_window_inside(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("22:00", "06:00", test_hour=23) is True

    def test_overnight_window_outside(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("22:00", "06:00", test_hour=12) is False

    def test_boundary_start(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("09:00", "17:00", test_hour=9) is True

    def test_boundary_end_exclusive(self):
        from kabot.heartbeat.service import is_within_active_hours
        assert is_within_active_hours("09:00", "17:00", test_hour=17) is False
```

**Step 2: Run test**

Run: `pytest tests/heartbeat/test_heartbeat_delivery.py -v`
Expected: FAIL — `ImportError: cannot import name 'HeartbeatDefaults'`

**Step 3: Write implementation**

Add to `kabot/config/schema.py`:

```python
class HeartbeatDefaults(BaseModel):
    """Heartbeat delivery routing and scheduling."""
    enabled: bool = True
    interval_minutes: int = 30
    target_channel: str = "last"   # "last", "none", or channel name
    target_to: str = ""            # Chat ID / phone number
    active_hours_start: str = ""   # "08:00" (24h), empty = always active
    active_hours_end: str = ""     # "22:00"
```

Add `is_within_active_hours()` to `kabot/heartbeat/service.py`:

```python
def is_within_active_hours(
    start: str, end: str, *, test_hour: int | None = None
) -> bool:
    """Check if current time is within active-hours window.

    Args:
        start: Start time "HH:MM" (24h). Empty = always active.
        end: End time "HH:MM" (24h). Empty = always active.
        test_hour: Override current hour for testing.

    Returns:
        True if within active hours or no hours configured.
    """
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
    # Overnight window (e.g. 22:00 → 06:00)
    return now_min >= start_min or now_min < end_min
```

Update `HeartbeatService._loop()` to call `is_within_active_hours()` before executing.

**Step 4: Run test**

Run: `pytest tests/heartbeat/test_heartbeat_delivery.py -v`
Expected: PASS (9 passed)

**Step 5: Commit**

```bash
git add kabot/config/schema.py kabot/heartbeat/service.py tests/heartbeat/test_heartbeat_delivery.py
git commit -m "feat(heartbeat): add HeartbeatDefaults with active-hours and delivery target"
```

---

## Task 4: Cron Delivery Modes (announce/webhook/none)

**Files:**
- Modify: `kabot/cron/types.py:22-35`
- Modify: `kabot/cron/delivery.py`
- Create: `tests/cron/test_cron_delivery_modes.py`

**Step 1: Write the failing test**

```python
"""Tests for cron delivery mode resolution."""
import pytest
from kabot.cron.delivery import resolve_delivery_plan
from kabot.cron.types import (
    CronJob, CronPayload, CronSchedule, CronDeliveryConfig,
)


class TestResolveDeliveryPlan:
    def test_announce_mode(self):
        job = CronJob(
            id="j1", name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi"),
            delivery=CronDeliveryConfig(
                mode="announce", channel="telegram", to="123",
            ),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "announce"
        assert plan["channel"] == "telegram"
        assert plan["to"] == "123"

    def test_webhook_mode(self):
        job = CronJob(
            id="j2", name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi"),
            delivery=CronDeliveryConfig(
                mode="webhook",
                webhook_url="https://example.com/hook",
            ),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "webhook"
        assert plan["webhook_url"] == "https://example.com/hook"

    def test_none_mode(self):
        job = CronJob(
            id="j3", name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi"),
            delivery=CronDeliveryConfig(mode="none"),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "none"

    def test_legacy_deliver_true_becomes_announce(self):
        job = CronJob(
            id="j4", name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(
                message="hi", deliver=True,
                channel="telegram", to="123",
            ),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "announce"

    def test_legacy_deliver_false_becomes_none(self):
        job = CronJob(
            id="j5", name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi", deliver=False),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "none"

    def test_no_delivery_no_deliver_flag_becomes_none(self):
        job = CronJob(
            id="j6", name="test",
            schedule=CronSchedule(kind="every"),
            payload=CronPayload(message="hi"),
        )
        plan = resolve_delivery_plan(job)
        assert plan["mode"] == "none"
```

**Step 2: Run test**

Run: `pytest tests/cron/test_cron_delivery_modes.py -v`
Expected: FAIL — `ImportError: cannot import name 'CronDeliveryConfig'`

**Step 3: Write implementation**

Add to `kabot/cron/types.py`:

```python
@dataclass
class CronDeliveryConfig:
    """Delivery configuration for a cron job result."""
    mode: Literal["announce", "webhook", "none"] = "announce"
    channel: str = "last"
    to: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""
```

Add field to `CronJob`:

```python
    delivery: CronDeliveryConfig | None = None
```

Rewrite `kabot/cron/delivery.py`:

```python
"""Cron delivery plan resolver."""

from kabot.cron.types import CronJob


def resolve_delivery_plan(job: CronJob) -> dict:
    """Resolve the delivery plan for a completed cron job.

    Supports new CronDeliveryConfig (announce/webhook/none)
    and legacy CronPayload.deliver boolean flag.
    """
    if job.delivery:
        d = job.delivery
        return {
            "mode": d.mode,
            "channel": d.channel if d.mode == "announce" else None,
            "to": d.to or None,
            "webhook_url": d.webhook_url if d.mode == "webhook" else None,
        }

    # Legacy fallback: CronPayload.deliver boolean
    p = job.payload
    if p.deliver:
        return {
            "mode": "announce",
            "channel": p.channel or "last",
            "to": p.to,
            "webhook_url": None,
        }
    return {"mode": "none", "channel": None, "to": None, "webhook_url": None}


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

**Step 4: Run test**

Run: `pytest tests/cron/test_cron_delivery_modes.py -v`
Expected: PASS (6 passed)

**Step 5: Commit**

```bash
git add kabot/cron/types.py kabot/cron/delivery.py tests/cron/test_cron_delivery_modes.py
git commit -m "feat(cron): add CronDeliveryConfig with announce/webhook/none modes"
```

---

## Task 5: Cron Webhook POST with HMAC

**Files:**
- Modify: `kabot/cron/service.py`
- Create: `tests/cron/test_cron_webhook_post.py`

**Step 1: Write the failing test**

```python
"""Tests for cron webhook POST delivery with HMAC signature."""
import json
import hashlib
import hmac
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from kabot.cron.service import deliver_webhook


class TestDeliverWebhook:
    @pytest.mark.asyncio
    async def test_successful_post(self):
        with patch("kabot.cron.service.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = MagicMock(status_code=200)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_httpx.AsyncClient.return_value = mock_client

            ok = await deliver_webhook(
                url="https://example.com/hook",
                job_id="j1",
                job_name="Test Job",
                output="Hello World",
            )
            assert ok is True
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_hmac_signature_header(self):
        with patch("kabot.cron.service.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = MagicMock(status_code=200)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_httpx.AsyncClient.return_value = mock_client

            await deliver_webhook(
                url="https://example.com/hook",
                job_id="j1",
                job_name="Test",
                output="data",
                secret="my_secret",
            )
            call_kwargs = mock_client.post.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "X-Kabot-Signature" in headers
            assert headers["X-Kabot-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_no_signature_without_secret(self):
        with patch("kabot.cron.service.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_response = MagicMock(status_code=200)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_httpx.AsyncClient.return_value = mock_client

            await deliver_webhook(
                url="https://example.com/hook",
                job_id="j1", job_name="t", output="o",
            )
            call_kwargs = mock_client.post.call_args
            headers = call_kwargs.kwargs.get("headers", {})
            assert "X-Kabot-Signature" not in headers

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self):
        with patch("kabot.cron.service.httpx") as mock_httpx:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("connection error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_httpx.AsyncClient.return_value = mock_client

            ok = await deliver_webhook(
                url="https://example.com/hook",
                job_id="j1", job_name="t", output="o",
            )
            assert ok is False
```

**Step 2: Run test** → FAIL

**Step 3: Write implementation**

Add to `kabot/cron/service.py`:

```python
import hashlib
import hmac as _hmac
import httpx

async def deliver_webhook(
    url: str,
    job_id: str,
    job_name: str,
    output: str,
    secret: str = "",
) -> bool:
    """POST cron job result to a webhook URL with optional HMAC-SHA256."""
    import json as _json
    body = _json.dumps({
        "job_id": job_id,
        "job_name": job_name,
        "output": output,
        "timestamp": _now_ms(),
    })
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secret:
        sig = _hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        headers["X-Kabot-Signature"] = f"sha256={sig}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, content=body, headers=headers)
            return 200 <= resp.status_code < 300
    except Exception as e:
        logger.error(f"Webhook delivery failed: {e}")
        return False
```

**Step 4: Run test** → PASS (4 passed)

**Step 5: Commit**

```bash
git add kabot/cron/service.py tests/cron/test_cron_webhook_post.py
git commit -m "feat(cron): add deliver_webhook() with HMAC-SHA256 signing"
```

---

## Task 6: Telegram Inline Keyboard Builder

**Files:**
- Modify: `kabot/channels/telegram.py`
- Create: `tests/channels/test_telegram_inline_keyboard.py`

**Step 1: Write the failing test**

```python
"""Tests for Telegram inline keyboard builder."""
import pytest
from kabot.channels.telegram import build_inline_keyboard


class TestBuildInlineKeyboard:
    def test_single_row(self):
        rows = [[
            {"text": "Yes", "callback_data": "yes"},
            {"text": "No", "callback_data": "no"},
        ]]
        markup = build_inline_keyboard(rows)
        assert markup is not None
        assert len(markup.inline_keyboard) == 1
        assert len(markup.inline_keyboard[0]) == 2
        assert markup.inline_keyboard[0][0].text == "Yes"
        assert markup.inline_keyboard[0][0].callback_data == "yes"

    def test_multiple_rows(self):
        rows = [
            [{"text": "A", "callback_data": "a"}],
            [{"text": "B", "callback_data": "b"}],
        ]
        markup = build_inline_keyboard(rows)
        assert len(markup.inline_keyboard) == 2

    def test_url_button(self):
        rows = [[{"text": "Visit", "url": "https://example.com"}]]
        markup = build_inline_keyboard(rows)
        btn = markup.inline_keyboard[0][0]
        assert btn.url == "https://example.com"
        assert btn.callback_data is None

    def test_empty_returns_none(self):
        assert build_inline_keyboard([]) is None

    def test_default_callback_data(self):
        rows = [[{"text": "Click Me"}]]
        markup = build_inline_keyboard(rows)
        assert markup.inline_keyboard[0][0].callback_data == "Click Me"
```

**Step 2: Run test** → FAIL

**Step 3: Write implementation**

Add to `kabot/channels/telegram.py` (after imports):

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_inline_keyboard(
    rows: list[list[dict]],
) -> InlineKeyboardMarkup | None:
    """Build an InlineKeyboardMarkup from a list of button row specs.

    Each button dict can have:
      - text (required): Button label
      - callback_data: Data sent on click
      - url: URL to open (mutually exclusive with callback_data)
    """
    if not rows:
        return None
    keyboard = []
    for row in rows:
        kb_row = []
        for btn in row:
            if "url" in btn:
                kb_row.append(InlineKeyboardButton(
                    text=btn["text"], url=btn["url"],
                ))
            else:
                kb_row.append(InlineKeyboardButton(
                    text=btn["text"],
                    callback_data=btn.get("callback_data", btn["text"]),
                ))
        keyboard.append(kb_row)
    return InlineKeyboardMarkup(keyboard)
```

**Step 4: Run test** → PASS (5 passed)

**Step 5: Commit**

```bash
git add kabot/channels/telegram.py tests/channels/test_telegram_inline_keyboard.py
git commit -m "feat(telegram): add build_inline_keyboard() for interactive buttons"
```

---

## Task 7: Telegram Callback Query Handler

**Files:**
- Modify: `kabot/channels/telegram.py`
- Create: `tests/channels/test_telegram_callback_query.py`

**Step 1: Write the failing test**

```python
"""Tests for Telegram callback query handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from kabot.channels.telegram import TelegramChannel


class TestCallbackQueryHandler:
    @pytest.mark.asyncio
    async def test_callback_query_publishes_inbound(self):
        """Button click should publish InboundMessage to bus."""
        config = MagicMock()
        config.token = "test:token"
        config.allow_from = []
        config.proxy = None
        bus = MagicMock()
        bus.publish_inbound = AsyncMock()

        channel = TelegramChannel(config, bus)

        update = MagicMock()
        update.callback_query.data = "approve_deploy"
        update.callback_query.from_user.id = 123
        update.callback_query.from_user.username = "testuser"
        update.callback_query.message.chat_id = 456
        update.callback_query.answer = AsyncMock()

        await channel._on_callback_query(update, MagicMock())

        bus.publish_inbound.assert_called_once()
        msg = bus.publish_inbound.call_args[0][0]
        assert msg.channel == "telegram"
        assert "approve_deploy" in msg.content
        assert msg.chat_id == "456"
```

**Step 2: Run test** → FAIL

**Step 3: Implement `_on_callback_query()`** in `TelegramChannel` and register `CallbackQueryHandler` in `start()`.

```python
async def _on_callback_query(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline button clicks."""
    query = update.callback_query
    await query.answer()  # Acknowledge the click

    user_id = str(query.from_user.id)
    chat_id = str(query.message.chat_id)
    callback_data = query.data or ""

    # Access control
    if self.config.allow_from and user_id not in self.config.allow_from:
        username = query.from_user.username or ""
        if username not in self.config.allow_from:
            return

    msg = InboundMessage(
        channel="telegram",
        sender_id=user_id,
        chat_id=chat_id,
        content=f"[Button clicked: {callback_data}]",
    )
    await self.bus.publish_inbound(msg)
```

In `start()`, add:

```python
from telegram.ext import CallbackQueryHandler
self._app.add_handler(CallbackQueryHandler(self._on_callback_query))
```

**Step 4: Run test** → PASS

**Step 5: Commit**

```bash
git add kabot/channels/telegram.py tests/channels/test_telegram_callback_query.py
git commit -m "feat(telegram): handle inline button callbacks via CallbackQueryHandler"
```

---

## Task 8: Discord Interactive Component Builder

**Files:**
- Create: `kabot/channels/discord_components.py`
- Create: `tests/channels/test_discord_components.py`

**Step 1: Write the failing test**

```python
"""Tests for Discord component builder."""
import pytest
from kabot.channels.discord_components import (
    build_action_row, ButtonStyle, build_select_menu,
)


class TestButtonStyle:
    def test_primary(self):
        assert ButtonStyle.PRIMARY == 1
    def test_danger(self):
        assert ButtonStyle.DANGER == 4
    def test_link(self):
        assert ButtonStyle.LINK == 5


class TestBuildActionRow:
    def test_basic_buttons(self):
        row = build_action_row(buttons=[
            {"label": "Approve", "style": ButtonStyle.SUCCESS, "custom_id": "approve"},
            {"label": "Reject", "style": ButtonStyle.DANGER, "custom_id": "reject"},
        ])
        assert row["type"] == 1  # ACTION_ROW
        assert len(row["components"]) == 2
        assert row["components"][0]["label"] == "Approve"
        assert row["components"][0]["style"] == 3  # SUCCESS
        assert row["components"][0]["custom_id"] == "approve"

    def test_link_button_has_url(self):
        row = build_action_row(buttons=[
            {"label": "Docs", "style": ButtonStyle.LINK, "url": "https://docs.kabot.dev"},
        ])
        assert row["components"][0]["url"] == "https://docs.kabot.dev"
        assert "custom_id" not in row["components"][0]

    def test_empty_buttons_raises(self):
        with pytest.raises(ValueError):
            build_action_row(buttons=[])


class TestBuildSelectMenu:
    def test_string_select(self):
        menu = build_select_menu(
            custom_id="model_pick",
            options=[
                {"label": "GPT-4", "value": "gpt4"},
                {"label": "Claude", "value": "claude"},
            ],
            placeholder="Pick a model",
        )
        assert menu["type"] == 1  # ACTION_ROW wrapper
        select = menu["components"][0]
        assert select["type"] == 3  # STRING_SELECT
        assert len(select["options"]) == 2
```

**Step 2: Run test** → FAIL

**Step 3: Create `kabot/channels/discord_components.py`**

```python
"""Discord interactive component builders (buttons, selects, action rows)."""

from enum import IntEnum


class ButtonStyle(IntEnum):
    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5


class ComponentType(IntEnum):
    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3


def build_action_row(buttons: list[dict]) -> dict:
    """Build a Discord Action Row containing buttons."""
    if not buttons:
        raise ValueError("Action row requires at least one button")
    components = []
    for btn in buttons:
        comp: dict = {
            "type": ComponentType.BUTTON,
            "label": btn["label"],
            "style": int(btn["style"]),
        }
        if btn["style"] == ButtonStyle.LINK:
            comp["url"] = btn["url"]
        else:
            comp["custom_id"] = btn.get("custom_id", btn["label"].lower().replace(" ", "_"))
        components.append(comp)
    return {"type": ComponentType.ACTION_ROW, "components": components}


def build_select_menu(
    custom_id: str,
    options: list[dict],
    placeholder: str = "",
    min_values: int = 1,
    max_values: int = 1,
) -> dict:
    """Build a Discord String Select Menu wrapped in an Action Row."""
    select = {
        "type": ComponentType.STRING_SELECT,
        "custom_id": custom_id,
        "options": [
            {"label": o["label"], "value": o["value"],
             "description": o.get("description", "")}
            for o in options
        ],
        "placeholder": placeholder,
        "min_values": min_values,
        "max_values": max_values,
    }
    return {"type": ComponentType.ACTION_ROW, "components": [select]}
```

**Step 4: Run test** → PASS (6 passed)

**Step 5: Commit**

```bash
git add kabot/channels/discord_components.py tests/channels/test_discord_components.py
git commit -m "feat(discord): add interactive component builder (buttons, selects)"
```

---

## Task 9: Discord Interaction Handler

**Files:**
- Modify: `kabot/channels/discord.py:134-170`
- Create: `tests/channels/test_discord_interaction_handler.py`

**Step 1: Write the failing test**

```python
"""Tests for Discord INTERACTION_CREATE handler."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from kabot.channels.discord import DiscordChannel


class TestInteractionHandler:
    @pytest.mark.asyncio
    async def test_button_interaction_publishes_inbound(self):
        config = MagicMock()
        config.token = "test_token"
        config.allow_from = []
        config.gateway_url = "wss://gateway.discord.gg"
        config.intents = 37377
        bus = MagicMock()
        bus.publish_inbound = AsyncMock()

        channel = DiscordChannel(config, bus)

        payload = {
            "type": 3,  # MESSAGE_COMPONENT
            "data": {"custom_id": "approve_deploy", "component_type": 2},
            "member": {"user": {"id": "123", "username": "testuser"}},
            "channel_id": "456",
            "id": "inter_001",
            "token": "interaction_token",
        }

        await channel._handle_interaction_create(payload)
        bus.publish_inbound.assert_called_once()
        msg = bus.publish_inbound.call_args[0][0]
        assert msg.channel == "discord"
        assert "approve_deploy" in msg.content
```

**Step 2: Run test** → FAIL

**Step 3: Implement** `_handle_interaction_create()` in `DiscordChannel` and add dispatch in `_gateway_loop()`:

```python
async def _handle_interaction_create(self, payload: dict) -> None:
    """Handle button/select interactions from Discord."""
    interaction_type = payload.get("type", 0)
    if interaction_type != 3:  # MESSAGE_COMPONENT only
        return

    data = payload.get("data", {})
    custom_id = data.get("custom_id", "")
    user = (payload.get("member", {}).get("user", {})
            or payload.get("user", {}))
    user_id = user.get("id", "")
    channel_id = payload.get("channel_id", "")

    if self.config.allow_from and user_id not in self.config.allow_from:
        return

    # ACK the interaction (type 6 = DEFERRED_UPDATE_MESSAGE)
    interaction_id = payload.get("id", "")
    interaction_token = payload.get("token", "")
    if interaction_id and interaction_token:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{DISCORD_API_BASE}/interactions/{interaction_id}/{interaction_token}/callback",
                json={"type": 6},
            )

    msg = InboundMessage(
        channel="discord",
        sender_id=user_id,
        chat_id=channel_id,
        content=f"[Button clicked: {custom_id}]",
    )
    await self.bus.publish_inbound(msg)
```

In `_gateway_loop()`, add dispatch for event `INTERACTION_CREATE`.

**Step 4: Run test** → PASS

**Step 5: Commit**

```bash
git add kabot/channels/discord.py tests/channels/test_discord_interaction_handler.py
git commit -m "feat(discord): handle INTERACTION_CREATE for button/select clicks"
```

---

## Task 10: Docker Sandbox Module

**Files:**
- Create: `kabot/sandbox/__init__.py`
- Create: `kabot/sandbox/docker_sandbox.py`
- Create: `Dockerfile.sandbox`
- Create: `tests/sandbox/test_docker_sandbox.py`

**Step 1: Write the failing test**

```python
"""Tests for Docker sandbox (Docker SDK mocked)."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from kabot.sandbox.docker_sandbox import DockerSandbox


class TestDockerSandbox:
    def test_default_is_inactive(self):
        sb = DockerSandbox(image="kabot-sandbox", mode="off")
        assert sb.is_active is False

    def test_active_when_mode_all(self):
        sb = DockerSandbox(image="kabot-sandbox", mode="all")
        assert sb.is_active is True

    def test_workspace_access_defaults_rw(self):
        sb = DockerSandbox(image="kabot-sandbox")
        assert sb.workspace_access == "rw"

    @pytest.mark.asyncio
    async def test_exec_returns_output(self):
        sb = DockerSandbox(image="test", mode="all")
        with patch.object(sb, "_run_in_container", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "hello world"
            result = await sb.exec_command("echo hello world")
            assert result == "hello world"

    @pytest.mark.asyncio
    async def test_exec_noop_when_inactive(self):
        sb = DockerSandbox(image="test", mode="off")
        result = await sb.exec_command("echo test")
        assert result is None
```

**Step 2: Run test** → FAIL

**Step 3: Create `kabot/sandbox/docker_sandbox.py`**

```python
"""Docker sandbox for isolated command execution."""
import asyncio
from loguru import logger


class DockerSandbox:
    """Execute commands inside a throw-away Docker container."""

    def __init__(
        self,
        image: str = "kabot-sandbox",
        mode: str = "off",
        workspace_access: str = "rw",
    ):
        self.image = image
        self.mode = mode
        self.workspace_access = workspace_access

    @property
    def is_active(self) -> bool:
        return self.mode in ("all", "non-main")

    async def exec_command(self, command: str, timeout: int = 60) -> str | None:
        if not self.is_active:
            return None
        return await self._run_in_container(command, timeout)

    async def _run_in_container(self, command: str, timeout: int = 60) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "-i", "kabot-sandbox-runner",
                "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            return f"[Sandbox timeout after {timeout}s]"
        except Exception as e:
            logger.error(f"Sandbox exec error: {e}")
            return f"[Sandbox error: {e}]"
```

Create `kabot/sandbox/__init__.py`:

```python
"""Docker sandbox for isolated agent command execution."""
```

Create `Dockerfile.sandbox`:

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl git jq ripgrep && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash sandbox
USER sandbox
WORKDIR /home/sandbox
CMD ["sleep", "infinity"]
```

**Step 4: Run test** → PASS (5 passed)

**Step 5: Commit**

```bash
git add kabot/sandbox/ Dockerfile.sandbox tests/sandbox/test_docker_sandbox.py
git commit -m "feat(sandbox): add DockerSandbox module for isolated command execution"
```

---

## Task 11: Security Audit Trail Logger

**Files:**
- Create: `kabot/security/audit_trail.py`
- Create: `tests/security/test_audit_trail.py`

**Step 1: Write the failing test**

```python
"""Tests for structured security audit trail."""
import json
import pytest
from pathlib import Path
from kabot.security.audit_trail import AuditTrail


@pytest.fixture
def audit(tmp_path):
    return AuditTrail(log_dir=tmp_path / "audit")


class TestAuditTrail:
    def test_log_creates_jsonl_file(self, audit, tmp_path):
        audit.log(event="command.exec", data={"cmd": "ls"})
        files = list((tmp_path / "audit").glob("*.jsonl"))
        assert len(files) == 1

    def test_log_entry_has_required_fields(self, audit, tmp_path):
        audit.log(event="tool.invoke", data={"tool": "shell"}, actor="agent:main")
        log_file = list((tmp_path / "audit").glob("*.jsonl"))[0]
        line = log_file.read_text().strip().split("\n")[0]
        entry = json.loads(line)
        assert entry["event"] == "tool.invoke"
        assert entry["actor"] == "agent:main"
        assert "timestamp" in entry
        assert "data" in entry

    def test_multiple_entries_append(self, audit, tmp_path):
        audit.log(event="a", data={})
        audit.log(event="b", data={})
        log_file = list((tmp_path / "audit").glob("*.jsonl"))[0]
        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_query_by_event_type(self, audit):
        audit.log(event="auth.login", data={"user": "admin"})
        audit.log(event="command.exec", data={"cmd": "rm -rf /"})
        audit.log(event="auth.login", data={"user": "bob"})
        results = audit.query(event="auth.login")
        assert len(results) == 2
```

**Step 2: Run test** → FAIL

**Step 3: Create `kabot/security/audit_trail.py`**

```python
"""Structured security audit trail (JSONL)."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger


class AuditTrail:
    """Append-only JSONL security audit log."""

    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._log_file = self.log_dir / f"audit-{date_str}.jsonl"

    def log(
        self,
        event: str,
        data: dict,
        actor: str = "system",
        severity: str = "info",
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch_ms": int(time.time() * 1000),
            "event": event,
            "actor": actor,
            "severity": severity,
            "data": data,
        }
        try:
            with open(self._log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Audit write failed: {e}")

    def query(self, event: str | None = None, limit: int = 100) -> list[dict]:
        results = []
        for log_file in sorted(self.log_dir.glob("*.jsonl"), reverse=True):
            for line in log_file.read_text().strip().split("\n"):
                if not line:
                    continue
                entry = json.loads(line)
                if event and entry.get("event") != event:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    return results
        return results
```

**Step 4: Run test** → PASS (4 passed)

**Step 5: Commit**

```bash
git add kabot/security/audit_trail.py tests/security/test_audit_trail.py
git commit -m "feat(security): add structured JSONL audit trail logger"
```

---

## Task 12: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md:8-9`

**Step 1: Insert new section under `## [Unreleased]`**

```markdown
### Added - Kabot Full-Parity Enhancements (2026-02-21)

- **Sub-agent Safety Limits:**
  - Added `SubagentDefaults` config: `max_spawn_depth`, `max_children_per_agent`, `archive_after_minutes`.
  - `SubagentManager.spawn()` now enforces concurrent-children and nesting-depth guards.
- **Heartbeat Delivery & Active Hours:**
  - Added `HeartbeatDefaults` config: `target_channel`, `target_to`, `active_hours_start/end`.
  - Heartbeat skips execution outside configured active-hours window.
- **Cron Webhook Delivery Modes:**
  - Added `CronDeliveryConfig`: `announce` (chat), `webhook` (HTTP POST), `none` (silent).
  - Webhook delivery includes HMAC-SHA256 signature (`X-Kabot-Signature` header).
  - Backward-compatible with legacy `deliver: true/false` format.
- **Telegram Inline Buttons:**
  - Added `build_inline_keyboard()` for `InlineKeyboardMarkup` creation.
  - Added `CallbackQueryHandler` for inline button click events.
- **Discord Interactive Components:**
  - Added `discord_components.py`: `build_action_row()`, `build_select_menu()`, `ButtonStyle`.
  - Added `INTERACTION_CREATE` handler for button and select interactions.
- **Docker Sandbox Execution (Optional):**
  - Added `kabot/sandbox/` module with `DockerSandbox` for isolated command execution.
  - Added `Dockerfile.sandbox` (Python 3.11 slim + bash/curl/git/jq/ripgrep).
- **Security Audit Trail:**
  - Added `AuditTrail` class — structured JSONL security logger with query support.
```

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG with full-parity enhancements"
```

---

## Task 13: Final Integration Test

**Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -40
```

Expected: All existing tests + 12 new test classes pass. No regressions.

**Step 2: Final commit and push**

```bash
git add -A
git commit -m "chore: final verification for Kabot full-parity roadmap"
git push
```
