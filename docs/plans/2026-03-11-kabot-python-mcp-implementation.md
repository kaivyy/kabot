# Kabot Python MCP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a safe, Python-native MCP foundation to Kabot with config schema, runtime skeleton, capability registry, and transcript helpers, without changing current agent behavior.

**Architecture:** Introduce a new `kabot.mcp` package that is isolated from the existing loop/runtime for now. Wire only typed config into the root schema, then add pure-Python support modules for server definitions, namespaced MCP tool registration, session-scoped runtime state, and transcript-safe synthetic error events.

**Tech Stack:** Python, Pydantic, pytest, existing Kabot config/runtime patterns

---

### Task 1: Add failing MCP config schema tests

**Files:**
- Create: `tests/config/test_mcp_config.py`
- Modify: none

**Step 1: Write the failing test**

```python
from pydantic import ValidationError

from kabot.config.schema import Config


def test_mcp_defaults_are_disabled():
    cfg = Config()
    assert cfg.mcp.enabled is False
    assert cfg.mcp.servers == {}


def test_stdio_mcp_server_requires_command():
    try:
        Config.model_validate(
            {
                "mcp": {
                    "enabled": True,
                    "servers": {
                        "local": {
                            "transport": "stdio",
                        }
                    },
                }
            }
        )
    except ValidationError as exc:
        assert "command" in str(exc)
    else:
        raise AssertionError("Expected ValidationError")


def test_streamable_http_mcp_server_requires_url():
    try:
        Config.model_validate(
            {
                "mcp": {
                    "enabled": True,
                    "servers": {
                        "remote": {
                            "transport": "streamable_http",
                        }
                    },
                }
            }
        )
    except ValidationError as exc:
        assert "url" in str(exc)
    else:
        raise AssertionError("Expected ValidationError")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/config/test_mcp_config.py -q`
Expected: FAIL because `Config` does not have an `mcp` section yet.

**Step 3: Write minimal implementation**

Add typed MCP config models in `kabot/config/schema.py`:

- `McpServerConfig`
- `McpConfig`
- attach `mcp: McpConfig = Field(default_factory=McpConfig)` to root `Config`

Required validation:

- `transport` supports `stdio` and `streamable_http`
- `stdio` requires `command`
- `streamable_http` requires `url`

**Step 4: Run test to verify it passes**

Run: `pytest tests/config/test_mcp_config.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/config/test_mcp_config.py kabot/config/schema.py
git commit -m "feat: add MCP config schema"
```

### Task 2: Add failing server-definition tests

**Files:**
- Create: `tests/mcp/test_config.py`
- Create: `kabot/mcp/models.py`
- Create: `kabot/mcp/config.py`

**Step 1: Write the failing test**

```python
from kabot.config.schema import Config
from kabot.mcp.config import resolve_mcp_server_definitions


def test_resolve_stdio_mcp_server_definition():
    cfg = Config.model_validate(
        {
            "mcp": {
                "enabled": True,
                "servers": {
                    "local_tools": {
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "example_server"],
                        "env": {"FOO": "bar"},
                    }
                },
            }
        }
    )

    resolved = resolve_mcp_server_definitions(cfg)
    assert [item.name for item in resolved] == ["local_tools"]
    assert resolved[0].transport == "stdio"
    assert resolved[0].command == "python"
    assert resolved[0].args == ["-m", "example_server"]
    assert resolved[0].env == {"FOO": "bar"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_config.py -q`
Expected: FAIL because `kabot.mcp.config` does not exist.

**Step 3: Write minimal implementation**

Create:

- `kabot/mcp/models.py`
- `kabot/mcp/config.py`

Add:

- immutable `McpServerDefinition`
- `resolve_mcp_server_definitions(cfg: Config) -> list[McpServerDefinition]`

Keep it pure and deterministic. No network calls, no SDK dependency yet.

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_config.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/mcp/test_config.py kabot/mcp/models.py kabot/mcp/config.py
git commit -m "feat: add MCP server definition resolver"
```

### Task 3: Add failing MCP capability registry tests

**Files:**
- Create: `tests/mcp/test_registry.py`
- Create: `kabot/mcp/registry.py`

**Step 1: Write the failing test**

```python
from kabot.mcp.models import McpToolDescriptor
from kabot.mcp.registry import McpCapabilityRegistry


def test_registry_namespaces_mcp_tools():
    registry = McpCapabilityRegistry()
    registry.register_tool(
        McpToolDescriptor(
            server_name="github",
            tool_name="list_prs",
            description="List pull requests",
        )
    )

    names = registry.tool_names()
    assert names == ["mcp.github.list_prs"]
    tool = registry.get_tool("mcp.github.list_prs")
    assert tool.description == "List pull requests"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_registry.py -q`
Expected: FAIL because registry classes do not exist.

**Step 3: Write minimal implementation**

Add:

- `McpToolDescriptor`
- `McpRegisteredTool`
- `McpCapabilityRegistry`

Rules:

- tool names must be namespaced as `mcp.<server>.<tool>`
- duplicate names raise `ValueError`

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_registry.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/mcp/test_registry.py kabot/mcp/models.py kabot/mcp/registry.py
git commit -m "feat: add MCP capability registry"
```

### Task 4: Add failing transcript helper tests

**Files:**
- Create: `tests/mcp/test_transcript.py`
- Create: `kabot/mcp/transcript.py`

**Step 1: Write the failing test**

```python
from kabot.mcp.transcript import make_mcp_missing_tool_result


def test_make_mcp_missing_tool_result_is_error_shaped():
    event = make_mcp_missing_tool_result(
        call_id="call-123",
        server_name="github",
        tool_name="list_prs",
    )

    assert event["role"] == "tool"
    assert event["tool_call_id"] == "call-123"
    assert event["tool_name"] == "mcp.github.list_prs"
    assert event["is_error"] is True
    assert "synthetic" in event["content"].lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_transcript.py -q`
Expected: FAIL because transcript helper does not exist.

**Step 3: Write minimal implementation**

Create `kabot/mcp/transcript.py` with a helper that creates a synthetic error result payload for missing MCP tool results. Keep it runtime-neutral and easy to adapt later to the exact loop transcript shape.

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_transcript.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/mcp/test_transcript.py kabot/mcp/transcript.py
git commit -m "feat: add MCP transcript repair helper"
```

### Task 5: Add failing session runtime skeleton tests

**Files:**
- Create: `tests/mcp/test_runtime.py`
- Create: `kabot/mcp/runtime.py`
- Create: `kabot/mcp/session_state.py`
- Create: `kabot/mcp/transports/__init__.py`

**Step 1: Write the failing test**

```python
from kabot.mcp.models import McpServerDefinition
from kabot.mcp.runtime import McpSessionRuntime


def test_session_runtime_tracks_attached_servers():
    runtime = McpSessionRuntime(session_id="s1")
    runtime.attach(
        McpServerDefinition(
            name="github",
            transport="streamable_http",
            url="https://example.com/mcp",
        )
    )

    assert runtime.attached_server_names() == ["github"]
    assert runtime.has_server("github") is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_runtime.py -q`
Expected: FAIL because session runtime does not exist.

**Step 3: Write minimal implementation**

Create:

- lightweight `McpSessionState`
- lightweight `McpSessionRuntime`

Scope:

- attach definitions
- inspect attached servers
- no network connection yet

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_runtime.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/mcp/test_runtime.py kabot/mcp/runtime.py kabot/mcp/session_state.py kabot/mcp/transports/__init__.py
git commit -m "feat: add MCP session runtime skeleton"
```

### Task 6: Export package surface and update changelog

**Files:**
- Create: `kabot/mcp/__init__.py`
- Modify: `CHANGELOG.md`

**Step 1: Write the failing test**

Add to `tests/mcp/test_config.py`:

```python
from kabot.mcp import McpSessionRuntime, resolve_mcp_server_definitions


def test_mcp_package_exports_stable_surface():
    assert McpSessionRuntime is not None
    assert callable(resolve_mcp_server_definitions)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/mcp/test_config.py -q`
Expected: FAIL because package exports are incomplete.

**Step 3: Write minimal implementation**

Export stable symbols from `kabot/mcp/__init__.py` and add a changelog entry describing:

- MCP full-Python design plan
- MCP schema and runtime scaffold

**Step 4: Run test to verify it passes**

Run: `pytest tests/mcp/test_config.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add kabot/mcp/__init__.py CHANGELOG.md tests/mcp/test_config.py
git commit -m "docs: document MCP Python scaffold"
```

### Task 7: Run focused verification

**Files:**
- Modify: none

**Step 1: Run focused test suite**

Run:

```bash
pytest tests/config/test_mcp_config.py tests/mcp/test_config.py tests/mcp/test_registry.py tests/mcp/test_transcript.py tests/mcp/test_runtime.py -q
```

Expected: PASS

**Step 2: Run lint on touched files**

Run:

```bash
ruff check kabot/config/schema.py kabot/mcp tests/config/test_mcp_config.py tests/mcp
```

Expected: `All checks passed!`

**Step 3: Commit**

```bash
git add .
git commit -m "test: verify MCP Python scaffold"
```

### Task 8: Optional wider safety verification

**Files:**
- Modify: none

**Step 1: Run broader config/runtime tests**

Run:

```bash
pytest tests/config tests/memory/test_memory_factory.py tests/cli/test_agent_runtime_config.py -q
```

Expected: PASS

**Step 2: Run full suite if time allows**

Run:

```bash
pytest tests -q
```

Expected: PASS

**Step 3: Commit**

```bash
git add .
git commit -m "chore: verify MCP scaffold against broader suite"
```
