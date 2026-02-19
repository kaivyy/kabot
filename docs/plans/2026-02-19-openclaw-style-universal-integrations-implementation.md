# OpenClaw-Style Universal Integrations (Meta + Multi-Bot) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Kabot so users can safely build "do anything" automations (including Meta Threads/Instagram) through secure API/webhook integrations, easier multi-bot setup, and plugin scaffolding.

**Architecture:** Follow OpenClaw's extensibility pattern: keep core small, add capability through plugins/tools/extensions. Implement a hardened HTTP integration layer (SSRF guard + signature validation), then expose Meta Graph actions as tools and webhook routes. Add fleet-oriented setup UX so multiple bots can be created and bound to different agents/models quickly.

**Tech Stack:** Python 3.11+, aiohttp, httpx, Pydantic, Typer, pytest.

---

### Task 1: Harden HTTP Integration Guard (Foundation)

**Files:**
- Modify: `kabot/config/schema.py`
- Modify: `kabot/agent/tools/web_fetch.py`
- Modify: `kabot/agent/loop.py`
- Modify: `kabot/agent/subagent.py`
- Test: `tests/config/test_integrations_config.py` (new)
- Test: `tests/tools/test_web_fetch_guard.py` (new)

**Step 1: Write the failing tests**

Create `tests/config/test_integrations_config.py`:

```python
from kabot.config.schema import Config


def test_integrations_defaults_are_safe():
    cfg = Config()
    assert cfg.integrations.http_guard.block_private_networks is True
    assert "169.254.169.254" in cfg.integrations.http_guard.deny_hosts
```

Create `tests/tools/test_web_fetch_guard.py`:

```python
import pytest
from kabot.agent.tools.web_fetch import WebFetchTool


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_host_by_default():
    tool = WebFetchTool()
    result = await tool.execute(url="http://127.0.0.1:8080/health")
    assert "blocked by network guard" in result.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/config/test_integrations_config.py tests/tools/test_web_fetch_guard.py -v`
Expected: FAIL (missing `integrations.http_guard` schema and no private-network blocking).

**Step 3: Write minimal implementation**

In `kabot/config/schema.py`, add:

```python
class HttpGuardConfig(BaseModel):
    block_private_networks: bool = True
    allow_hosts: list[str] = Field(default_factory=list)
    deny_hosts: list[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "169.254.169.254",
            "metadata.google.internal",
        ]
    )


class IntegrationsConfig(BaseModel):
    http_guard: HttpGuardConfig = Field(default_factory=HttpGuardConfig)


class Config(BaseSettings):
    ...
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
```

In `kabot/agent/tools/web_fetch.py`, add URL/host guard logic:

```python
def _validate_target(self, url: str) -> None:
    # parse scheme/host, block deny_hosts/private IPs, enforce allow_hosts if configured
    ...
```

In `kabot/agent/loop.py` and `kabot/agent/subagent.py`, pass guard config into `WebFetchTool(...)`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/config/test_integrations_config.py tests/tools/test_web_fetch_guard.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/config/schema.py kabot/agent/tools/web_fetch.py kabot/agent/loop.py kabot/agent/subagent.py tests/config/test_integrations_config.py tests/tools/test_web_fetch_guard.py
git commit -m "feat(security): add http integration guard and safe defaults"
```

---

### Task 2: Add Meta Graph API Tool (Threads + Instagram outbound)

**Files:**
- Create: `kabot/integrations/meta_graph.py`
- Create: `kabot/agent/tools/meta_graph.py`
- Modify: `kabot/agent/loop.py`
- Modify: `kabot/agent/subagent.py`
- Modify: `kabot/config/schema.py`
- Test: `tests/tools/test_meta_graph_tool.py` (new)

**Step 1: Write the failing test**

Create `tests/tools/test_meta_graph_tool.py`:

```python
import pytest
from kabot.agent.tools.meta_graph import MetaGraphTool


@pytest.mark.asyncio
async def test_meta_graph_threads_create_uses_expected_endpoint(monkeypatch):
    sent = {}

    class FakeClient:
        async def request(self, method, path, payload):
            sent["method"] = method
            sent["path"] = path
            sent["payload"] = payload
            return {"id": "creation-1"}

    tool = MetaGraphTool(client=FakeClient())
    await tool.execute(action="threads_create", text="hello world")
    assert sent["method"] == "POST"
    assert sent["path"].endswith("/threads")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_meta_graph_tool.py::test_meta_graph_threads_create_uses_expected_endpoint -v`
Expected: FAIL (tool/module missing).

**Step 3: Write minimal implementation**

Create `kabot/integrations/meta_graph.py`:

```python
class MetaGraphClient:
    async def request(self, method: str, path: str, payload: dict) -> dict:
        # httpx call to graph.facebook.com with bearer access token
        ...
```

Create `kabot/agent/tools/meta_graph.py`:

```python
class MetaGraphTool(Tool):
    # actions: threads_create, threads_publish, ig_media_create, ig_media_publish
    async def execute(self, action: str, **kwargs):
        ...
```

Register tool in `kabot/agent/loop.py` and `kabot/agent/subagent.py`:

```python
self.tools.register(MetaGraphTool(config=self.config))
```

Add Meta config fields in `kabot/config/schema.py`:

```python
class MetaIntegrationConfig(BaseModel):
    enabled: bool = False
    access_token: str = ""
    app_secret: str = ""
    verify_token: str = ""
    threads_user_id: str = ""
    instagram_user_id: str = ""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_meta_graph_tool.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/integrations/meta_graph.py kabot/agent/tools/meta_graph.py kabot/agent/loop.py kabot/agent/subagent.py kabot/config/schema.py tests/tools/test_meta_graph_tool.py
git commit -m "feat(integrations): add meta graph tool for threads and instagram actions"
```

---

### Task 3: Add Meta Webhook Endpoint with Signature Verification

**Files:**
- Create: `kabot/integrations/meta_webhook.py`
- Modify: `kabot/gateway/webhook_server.py`
- Test: `tests/gateway/test_webhooks_meta.py` (new)

**Step 1: Write the failing tests**

Create `tests/gateway/test_webhooks_meta.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_meta_webhook_verification_challenge(aiohttp_client):
    from kabot.gateway.webhook_server import WebhookServer
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    server = WebhookServer(bus=bus, meta_verify_token="verify-me", meta_app_secret="secret")
    client = await aiohttp_client(server.app)
    resp = await client.get("/webhooks/meta?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=123")
    assert resp.status == 200
    assert await resp.text() == "123"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/gateway/test_webhooks_meta.py -v`
Expected: FAIL (`/webhooks/meta` route missing).

**Step 3: Write minimal implementation**

In `kabot/gateway/webhook_server.py`:

```python
self.app.router.add_get("/webhooks/meta", self.handle_meta_verify)
self.app.router.add_post("/webhooks/meta", self.handle_meta_event)
```

Add signature verification in `kabot/integrations/meta_webhook.py`:

```python
def verify_meta_signature(raw_body: bytes, app_secret: str, signature_header: str) -> bool:
    expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")
```

Map valid events to `InboundMessage(channel="meta:threads", ...)` and publish to bus.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/gateway/test_webhooks_meta.py tests/gateway/test_webhooks.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/gateway/webhook_server.py kabot/integrations/meta_webhook.py tests/gateway/test_webhooks_meta.py
git commit -m "feat(gateway): add verified meta webhook ingress routing"
```

---

### Task 4: Fleet Builder in Setup Wizard (Multi-Bot + Multi-AI Fast Setup)

**Files:**
- Modify: `kabot/cli/setup_wizard.py`
- Create: `kabot/cli/fleet_templates.py`
- Test: `tests/cli/test_setup_wizard_fleet_builder.py` (new)

**Step 1: Write the failing test**

Create `tests/cli/test_setup_wizard_fleet_builder.py`:

```python
from pathlib import Path
from kabot.cli.setup_wizard import SetupWizard


def test_apply_fleet_template_creates_instances_and_agents(monkeypatch, tmp_path):
    monkeypatch.setattr("kabot.cli.setup_wizard.Path.home", lambda: Path(tmp_path))
    wizard = SetupWizard()
    wizard._apply_fleet_template(
        template_id="content_pipeline",
        channel_type="telegram",
        base_id="team",
        bot_tokens=["tok1", "tok2", "tok3"],
    )
    assert len(wizard.config.channels.instances) == 3
    assert len(wizard.config.agents.agents) >= 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_setup_wizard_fleet_builder.py -v`
Expected: FAIL (`_apply_fleet_template` missing).

**Step 3: Write minimal implementation**

Create `kabot/cli/fleet_templates.py`:

```python
FLEET_TEMPLATES = {
    "content_pipeline": [
        {"role": "ideation", "default_model": "anthropic/claude-3-5-sonnet-latest"},
        {"role": "research", "default_model": "openai/gpt-4.1"},
        {"role": "publish", "default_model": "openai-codex/gpt-5.3-codex"},
    ]
}
```

In `kabot/cli/setup_wizard.py`, add menu option under channel instances:

```python
questionary.Choice("Apply Fleet Template", value="template")
```

Implement `_apply_fleet_template(...)` to:
- create agents per template role,
- create channel instances,
- auto-bind each instance to its role agent.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/cli/test_setup_wizard_fleet_builder.py tests/cli/test_setup_wizard_channel_instances.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/cli/setup_wizard.py kabot/cli/fleet_templates.py tests/cli/test_setup_wizard_fleet_builder.py
git commit -m "feat(setup): add fleet templates for multi-bot multi-ai configuration"
```

---

### Task 5: Plugin Scaffold Command (OpenClaw-style "skill creator" workflow)

**Files:**
- Create: `kabot/plugins/scaffold.py`
- Create: `kabot/plugins/templates/dynamic/main.py.tpl`
- Create: `kabot/plugins/templates/dynamic/plugin.json.tpl`
- Modify: `kabot/cli/commands.py`
- Test: `tests/plugins/test_scaffold.py` (new)
- Modify: `tests/cli/test_plugins_commands.py`

**Step 1: Write the failing tests**

Create `tests/plugins/test_scaffold.py`:

```python
from kabot.plugins.scaffold import scaffold_plugin


def test_scaffold_creates_dynamic_plugin(tmp_path):
    out = scaffold_plugin(tmp_path, name="meta_bridge", kind="dynamic")
    assert (out / "plugin.json").exists()
    assert (out / "main.py").exists()
```

Add to `tests/cli/test_plugins_commands.py`:

```python
def test_plugins_scaffold_command(runner, monkeypatch, tmp_path):
    from kabot.cli.commands import app
    from kabot.config.schema import Config
    cfg = Config()
    cfg.agents.defaults.workspace = str(tmp_path / "workspace")
    monkeypatch.setattr("kabot.config.loader.load_config", lambda: cfg)
    result = runner.invoke(app, ["plugins", "scaffold", "--target", "meta_bridge"])
    assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/plugins/test_scaffold.py tests/cli/test_plugins_commands.py::test_plugins_scaffold_command -v`
Expected: FAIL (scaffold module/CLI action missing).

**Step 3: Write minimal implementation**

Create `kabot/plugins/scaffold.py`:

```python
def scaffold_plugin(base_dir: Path, name: str, kind: str = "dynamic") -> Path:
    # sanitize name, create folder, render template files
    ...
```

In `kabot/cli/commands.py`, extend plugins action set with `scaffold`:

```python
help="Action: list|install|update|enable|disable|remove|doctor|scaffold"
```

And action handler:

```python
if action == "scaffold":
    from kabot.plugins.scaffold import scaffold_plugin
    ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/plugins/test_scaffold.py tests/cli/test_plugins_commands.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/plugins/scaffold.py kabot/plugins/templates/dynamic/main.py.tpl kabot/plugins/templates/dynamic/plugin.json.tpl kabot/cli/commands.py tests/plugins/test_scaffold.py tests/cli/test_plugins_commands.py
git commit -m "feat(plugins): add scaffold command for dynamic plugin creation"
```

---

### Task 6: OAuth Parity Audit Command for All Providers

**Files:**
- Modify: `kabot/auth/menu.py`
- Modify: `kabot/auth/manager.py`
- Modify: `kabot/cli/commands.py`
- Test: `tests/auth/test_oauth_provider_parity.py` (new)
- Test: `tests/cli/test_auth_commands.py`

**Step 1: Write the failing tests**

Create `tests/auth/test_oauth_provider_parity.py`:

```python
from kabot.auth.menu import AUTH_PROVIDERS


def test_oauth_methods_have_valid_handlers():
    for provider_id, meta in AUTH_PROVIDERS.items():
        for method_id, method in meta["methods"].items():
            if method_id == "oauth":
                assert method["handler"].startswith("kabot.auth.handlers.")
```

Add CLI test in `tests/cli/test_auth_commands.py`:

```python
def test_auth_parity_command_exists(runner):
    from kabot.cli.commands import app
    result = runner.invoke(app, ["auth", "parity"])
    assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/auth/test_oauth_provider_parity.py tests/cli/test_auth_commands.py::test_auth_parity_command_exists -v`
Expected: FAIL (`auth parity` command missing).

**Step 3: Write minimal implementation**

In `kabot/auth/manager.py`, add a parity report helper:

```python
def parity_report(self) -> dict:
    # verify OAuth handlers import, provider aliases map correctly, and report gaps
    ...
```

In `kabot/cli/commands.py`, add:

```python
@auth_app.command("parity")
def auth_parity():
    ...
```

In `kabot/auth/menu.py`, ensure provider descriptions/labels are explicit for OAuth-capable providers.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/auth/test_oauth_provider_parity.py tests/cli/test_auth_commands.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add kabot/auth/menu.py kabot/auth/manager.py kabot/cli/commands.py tests/auth/test_oauth_provider_parity.py tests/cli/test_auth_commands.py
git commit -m "feat(auth): add oauth parity diagnostics across providers"
```

---

### Task 7: Documentation + Changelog + End-to-End Verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/OPENCLAW_VS_KABOT_COMPLETE_ANALYSIS.md` (if Kabot-side mirror exists, update that one)
- Create: `docs/integrations/meta-threads-instagram.md`

**Step 1: Add docs tests/check script (optional quick guard)**

Create or update a lightweight docs check entry in CI script if available:

```bash
rg -n "meta_graph|webhooks/meta|plugins scaffold|auth parity" README.md docs
```

**Step 2: Update docs content**

Document:
- how Meta outbound actions work (`meta_graph` tool),
- how Meta webhook verification works,
- how to configure fleet templates in setup wizard,
- how to scaffold custom plugins.

**Step 3: Update changelog**

Add one cohesive entry under `[Unreleased]` summarizing:
- integration guard,
- Meta tool/webhook,
- fleet templates,
- plugin scaffold,
- auth parity diagnostics.

**Step 4: Run verification suite**

Run:
- `pytest tests/tools/test_web_fetch_guard.py tests/tools/test_meta_graph_tool.py -v`
- `pytest tests/gateway/test_webhooks_meta.py tests/cli/test_setup_wizard_fleet_builder.py -v`
- `pytest tests/plugins/test_scaffold.py tests/auth/test_oauth_provider_parity.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md CHANGELOG.md docs/integrations/meta-threads-instagram.md docs/OPENCLAW_VS_KABOT_COMPLETE_ANALYSIS.md
git commit -m "docs: add meta integration, fleet setup, and parity guidance"
```

---

Plan complete and saved to `docs/plans/2026-02-19-openclaw-style-universal-integrations-implementation.md`. Two execution options:

1. **Subagent-Driven (this session)** - Execute task-by-task now in this session with checkpoints after each task.
2. **Parallel Session (separate)** - Open a fresh implementation session using the executing-plans flow.

Which approach?
