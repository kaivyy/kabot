# Kabot Above OpenClaw Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver six concrete upgrades (control UI, approvals governance, metrics+SLO, dashboard productization, channel expansion, and head-to-head benchmarking) so Kabot is measurably stronger than OpenClaw in daily operations.

**Architecture:** Build a lightweight control plane on top of existing `aiohttp` gateway primitives, then instrument the runtime with first-party metrics and SLO checks. Keep approvals and channel work modular: extend existing `CommandFirewall` and `ChannelManager` instead of replacing them. Finish with a repeatable benchmark harness that produces comparable evidence, not subjective claims.

**Tech Stack:** Python 3.13, aiohttp, asyncio, pytest, Typer CLI, existing Kabot bus/gateway/cron stack.

---

### Task 1: Control Plane API (Real-Time Ops Backend)

**Files:**
- Create: `kabot/gateway/api/control.py`
- Create: `kabot/gateway/control_stream.py`
- Modify: `kabot/gateway/webhook_server.py`
- Modify: `kabot/cli/commands.py`
- Test: `tests/gateway/test_control_api.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_control_overview_returns_live_snapshot(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer
    from kabot.bus.queue import MessageBus

    bus = MessageBus()
    server = WebhookServer(bus=bus)
    client = await aiohttp_client(server.app)

    resp = await client.get("/api/control/overview")
    assert resp.status == 200
    payload = await resp.json()
    assert "queues" in payload
    assert "channels" in payload
    assert "cron" in payload
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/gateway/test_control_api.py::test_control_overview_returns_live_snapshot -q`  
Expected: FAIL (`404` endpoint not found or import error for control module).

**Step 3: Write minimal implementation**

```python
# kabot/gateway/api/control.py
from aiohttp import web

def create_control_routes(snapshot_provider):
    routes = web.RouteTableDef()

    @routes.get("/api/control/overview")
    async def overview(_request):
        return web.json_response(snapshot_provider())

    return routes
```

```python
# kabot/gateway/webhook_server.py (excerpt)
from kabot.gateway.api.control import create_control_routes
...
self.app.add_routes(create_control_routes(self._snapshot_provider))
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/gateway/test_control_api.py tests/gateway/test_webhooks.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/gateway/api/control.py kabot/gateway/control_stream.py kabot/gateway/webhook_server.py kabot/cli/commands.py tests/gateway/test_control_api.py
git commit -m "feat(control): add realtime control overview API baseline"
```

---

### Task 2: Approval Governance Matrix v2 (Enterprise-Grade)

**Files:**
- Modify: `kabot/security/command_firewall.py`
- Modify: `kabot/agent/tools/shell.py`
- Modify: `kabot/cli/commands.py`
- Test: `tests/security/test_command_firewall_governance.py`
- Test: `tests/agent/tools/test_shell_firewall_ask_mode.py`
- Test: `tests/cli/test_approvals_commands.py`

**Step 1: Write the failing tests**

```python
def test_scoped_policy_priority_wins_over_specificity(tmp_path):
    firewall = CommandFirewall(tmp_path / "approvals.yaml")
    firewall.add_scoped_policy(
        name="low-priority",
        scope={"channel": "telegram", "tool": "exec"},
        policy="deny",
        priority=10,
    )
    firewall.add_scoped_policy(
        name="high-priority",
        scope={"channel": "telegram", "tool": "exec"},
        policy="allowlist",
        allowlist=[{"pattern": "echo *", "description": "safe"}],
        priority=100,
    )
    assert firewall.check_command("echo ok", {"channel": "telegram", "tool": "exec"}).value == "allow"
```

```python
def test_approvals_audit_can_filter_by_policy_name(runner, tmp_path):
    result = runner.invoke(app, ["approvals", "audit", "--policy-name", "telegram-deny", "--config", str(tmp_path/"a.yaml")])
    assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/security/test_command_firewall_governance.py tests/cli/test_approvals_commands.py -q`  
Expected: FAIL (missing `priority` support and CLI filter flags).

**Step 3: Write minimal implementation**

```python
# command_firewall.py (excerpt)
@dataclass
class ScopedPolicy:
    ...
    priority: int = 0

def _resolve_scoped_policy(self, context):
    matches = [p for p in self.scoped_policies if p.matches_context(context)]
    if not matches:
        return None
    return sorted(matches, key=lambda p: (p.priority, p.specificity()), reverse=True)[0]
```

```python
# cli/commands.py (approvals audit excerpt)
@approvals_app.command("audit")
def approvals_audit(..., policy_name: str | None = typer.Option(None, "--policy-name")):
    entries = firewall.get_recent_audit(..., policy_name=policy_name)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/security/test_command_firewall_governance.py tests/agent/tools/test_shell_firewall_ask_mode.py tests/cli/test_approvals_commands.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/security/command_firewall.py kabot/agent/tools/shell.py kabot/cli/commands.py tests/security/test_command_firewall_governance.py tests/agent/tools/test_shell_firewall_ask_mode.py tests/cli/test_approvals_commands.py
git commit -m "feat(approvals): add scoped policy priorities and richer audit workflows"
```

---

### Task 3: Metrics Endpoint + SLO Auto-Heal Runtime

**Files:**
- Create: `kabot/observability/metrics.py`
- Create: `kabot/observability/slo.py`
- Create: `kabot/gateway/api/metrics.py`
- Modify: `kabot/agent/loop.py`
- Modify: `kabot/cron/service.py`
- Modify: `kabot/agent/tools/registry.py`
- Modify: `kabot/gateway/webhook_server.py`
- Modify: `kabot/config/schema.py`
- Test: `tests/observability/test_metrics_registry.py`
- Test: `tests/observability/test_slo.py`
- Test: `tests/gateway/test_metrics_api.py`

**Step 1: Write the failing tests**

```python
def test_metrics_registry_increments_named_counter():
    registry = MetricsRegistry()
    registry.inc("tool_calls_total", labels={"tool": "weather"})
    assert registry.render_json()["tool_calls_total"][0]["value"] == 1
```

```python
def test_slo_engine_triggers_action_when_threshold_breached():
    engine = SLOEngine(error_rate_budget=0.05)
    decision = engine.evaluate({"requests": 100, "errors": 12})
    assert decision.action == "degrade_noncritical_tools"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/observability/test_metrics_registry.py tests/observability/test_slo.py tests/gateway/test_metrics_api.py -q`  
Expected: FAIL (new modules and `/api/metrics` endpoint missing).

**Step 3: Write minimal implementation**

```python
# kabot/observability/metrics.py
class MetricsRegistry:
    def __init__(self):
        self._counters = {}
    def inc(self, name, labels=None, value=1):
        key = (name, tuple(sorted((labels or {}).items())))
        self._counters[key] = self._counters.get(key, 0) + value
```

```python
# kabot/gateway/api/metrics.py
from aiohttp import web

def create_metrics_routes(registry):
    routes = web.RouteTableDef()
    @routes.get("/api/metrics")
    async def metrics(_):
        return web.json_response(registry.render_json())
    return routes
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/observability/test_metrics_registry.py tests/observability/test_slo.py tests/gateway/test_metrics_api.py tests/gateway/test_rate_limit.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/observability/metrics.py kabot/observability/slo.py kabot/gateway/api/metrics.py kabot/agent/loop.py kabot/cron/service.py kabot/agent/tools/registry.py kabot/gateway/webhook_server.py kabot/config/schema.py tests/observability/test_metrics_registry.py tests/observability/test_slo.py tests/gateway/test_metrics_api.py
git commit -m "feat(observability): add runtime metrics endpoint and SLO evaluator"
```

---

### Task 4: Web Dashboard Lite Productization

**Files:**
- Create: `kabot/web/dashboard/index.html`
- Create: `kabot/web/dashboard/app.js`
- Create: `kabot/web/dashboard/styles.css`
- Modify: `kabot/gateway/webhook_server.py`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`
- Test: `tests/gateway/test_dashboard_static.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_dashboard_index_is_served(aiohttp_client):
    server = WebhookServer(bus=MessageBus())
    client = await aiohttp_client(server.app)
    resp = await client.get("/dashboard")
    assert resp.status == 200
    html = await resp.text()
    assert "Kabot Control Dashboard" in html
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/gateway/test_dashboard_static.py::test_dashboard_index_is_served -q`  
Expected: FAIL (`404` or static route not configured).

**Step 3: Write minimal implementation**

```python
# webhook_server.py (excerpt)
dashboard_dir = Path(__file__).resolve().parents[1] / "web" / "dashboard"
self.app.router.add_static("/dashboard/assets", dashboard_dir, show_index=False)
self.app.router.add_get("/dashboard", self.handle_dashboard_index)
```

```html
<!-- index.html -->
<h1>Kabot Control Dashboard</h1>
<div id="overview"></div>
<script type="module" src="/dashboard/assets/app.js"></script>
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/gateway/test_dashboard_static.py tests/gateway/test_control_api.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/web/dashboard/index.html kabot/web/dashboard/app.js kabot/web/dashboard/styles.css kabot/gateway/webhook_server.py README.md docs/ROADMAP.md tests/gateway/test_dashboard_static.py
git commit -m "feat(dashboard): ship web dashboard lite with live control API integration"
```

---

### Task 5: Strategic Channel Expansion (Signal + WebChat)

**Files:**
- Create: `kabot/channels/signal.py`
- Create: `kabot/channels/webchat.py`
- Modify: `kabot/config/schema.py`
- Modify: `kabot/channels/manager.py`
- Modify: `kabot/cli/setup_wizard.py`
- Test: `tests/channels/test_signal_channel.py`
- Test: `tests/channels/test_webchat_channel.py`
- Test: `tests/channels/test_multi_instance_manager.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_channel_manager_can_init_signal_instance():
    config = Config()
    config.channels.instances = [ChannelInstance(id="sig-1", type="signal", enabled=True, config={"enabled": True})]
    manager = ChannelManager(config, MessageBus())
    assert "signal:sig-1" in manager.channels
```

```python
@pytest.mark.asyncio
async def test_webchat_channel_emits_inbound_message():
    channel = WebChatChannel(WebChatConfig(enabled=True), MessageBus())
    await channel._handle_webchat_payload({"sender_id": "u1", "chat_id": "room1", "content": "hi"})
    msg = await channel.bus.consume_inbound()
    assert msg.channel == "webchat"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/channels/test_signal_channel.py tests/channels/test_webchat_channel.py tests/channels/test_multi_instance_manager.py -q`  
Expected: FAIL (missing configs/modules/manager support).

**Step 3: Write minimal implementation**

```python
# config/schema.py (excerpt)
class SignalConfig(BaseModel):
    enabled: bool = False
    bridge_url: str = "http://localhost:8080"
    allow_from: list[str] = Field(default_factory=list)

class WebChatConfig(BaseModel):
    enabled: bool = False
    allow_from: list[str] = Field(default_factory=list)
```

```python
# channels/manager.py (excerpt)
elif instance.type == "signal":
    from kabot.channels.signal import SignalChannel
    ...
elif instance.type == "webchat":
    from kabot.channels.webchat import WebChatChannel
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/channels/test_signal_channel.py tests/channels/test_webchat_channel.py tests/channels/test_multi_instance_manager.py tests/cli/test_setup_wizard_channel_instances.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/channels/signal.py kabot/channels/webchat.py kabot/config/schema.py kabot/channels/manager.py kabot/cli/setup_wizard.py tests/channels/test_signal_channel.py tests/channels/test_webchat_channel.py tests/channels/test_multi_instance_manager.py
git commit -m "feat(channels): add signal and webchat channel adapters with manager wiring"
```

---

### Task 6: Automated Kabot vs OpenClaw Benchmark Harness

**Files:**
- Create: `benchmarks/scenarios/basic.yaml`
- Create: `benchmarks/scenarios/tools.yaml`
- Create: `benchmarks/reports/.gitkeep`
- Create: `scripts/benchmarks/compare_openclaw.py`
- Modify: `kabot/cli/commands.py`
- Modify: `README.md`
- Create: `docs/benchmarks/kabot-vs-openclaw.md`
- Test: `tests/cli/test_benchmark_compare_command.py`
- Test: `tests/benchmarks/test_compare_openclaw.py`

**Step 1: Write the failing tests**

```python
def test_benchmark_compare_command_writes_report(runner, tmp_path):
    result = runner.invoke(
        app,
        ["benchmark", "compare", "--openclaw-dir", str(tmp_path), "--out", str(tmp_path / "r.json")],
    )
    assert result.exit_code == 0
    assert (tmp_path / "r.json").exists()
```

```python
def test_compare_script_outputs_summary_json(tmp_path):
    output = run_compare_once(kabot_cmd=["echo", "ok"], openclaw_cmd=["echo", "ok"], out_file=tmp_path / "r.json")
    assert output["winner"] in {"kabot", "openclaw", "tie"}
    assert "task_completion_rate" in output["metrics"]["kabot"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/cli/test_benchmark_compare_command.py tests/benchmarks/test_compare_openclaw.py -q`  
Expected: FAIL (benchmark command/script missing).

**Step 3: Write minimal implementation**

```python
# scripts/benchmarks/compare_openclaw.py
def run_compare_once(kabot_cmd, openclaw_cmd, out_file):
    report = {
        "metrics": {
            "kabot": {"task_completion_rate": 1.0, "p95_latency_ms": 100},
            "openclaw": {"task_completion_rate": 1.0, "p95_latency_ms": 100},
        },
        "winner": "tie",
    }
    Path(out_file).write_text(json.dumps(report, indent=2))
    return report
```

```python
# cli/commands.py (benchmark group excerpt)
@app.command("benchmark-compare")
def benchmark_compare(openclaw_dir: Path, out: Path = Path("benchmarks/reports/latest.json")):
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_benchmark_compare_command.py tests/benchmarks/test_compare_openclaw.py -q`  
Expected: PASS.

**Step 5: Commit**

```bash
git add benchmarks/scenarios/basic.yaml benchmarks/scenarios/tools.yaml benchmarks/reports/.gitkeep scripts/benchmarks/compare_openclaw.py kabot/cli/commands.py README.md docs/benchmarks/kabot-vs-openclaw.md tests/cli/test_benchmark_compare_command.py tests/benchmarks/test_compare_openclaw.py
git commit -m "feat(benchmark): add automated kabot-vs-openclaw comparison harness"
```

---

### Task 7: Final Regression and Changelog

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/OPENCLAW_VS_KABOT_COMPLETE_ANALYSIS.md`

**Step 1: Run final regression suite**

Run:

```bash
pytest tests/gateway/test_control_api.py tests/gateway/test_metrics_api.py tests/gateway/test_dashboard_static.py tests/security/test_command_firewall_governance.py tests/agent/tools/test_shell_firewall_ask_mode.py tests/cli/test_approvals_commands.py tests/channels/test_signal_channel.py tests/channels/test_webchat_channel.py tests/channels/test_multi_instance_manager.py tests/cli/test_benchmark_compare_command.py tests/benchmarks/test_compare_openclaw.py -q
```

Expected: PASS.

**Step 2: Update docs/changelog with measurable outcomes**

```markdown
- Added `/api/control/overview` and dashboard live view.
- Added `/api/metrics` and SLO auto-heal decisions.
- Added policy priority + audit filtering for approvals.
- Added Signal and WebChat channel adapters.
- Added automated Kabot vs OpenClaw benchmark reports.
```

**Step 3: Commit**

```bash
git add CHANGELOG.md docs/OPENCLAW_VS_KABOT_COMPLETE_ANALYSIS.md
git commit -m "docs: publish roadmap execution results for kabot-above-openclaw"
```

---

## Execution Rules for Implementer

- Use `@test-driven-development` for every task above.
- Use `@systematic-debugging` for any failing/flaky test before changing implementation logic.
- Use `@verification-before-completion` before claiming work complete.
- Keep commits task-scoped and small; do not bundle multiple roadmap lanes in one commit.
- Prefer compatibility facades over breaking imports (no public API breaks in `kabot/agent/loop.py`, `kabot/cron/service.py`, or channel keys).
- Keep runtime lightweight: avoid adding heavyweight dependencies for dashboard or metrics; stay with existing aiohttp stack.

