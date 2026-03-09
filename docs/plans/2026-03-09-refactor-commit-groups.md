# Commit Grouping Plan

**Branch:** `main`

**Verification run on current workspace**

```powershell
pytest tests/agent tests/cli tests/gateway -q
# 832 passed

ruff check .
# Fails only because local scratch file `test_session_delete.py` is untracked

$files = git ls-files '*.py' | Where-Object { Test-Path $_ }
ruff check $files
# All checks passed
```

**Important**

- `test_session_delete.py`, `test_dashboard_plan.md`, and `memory/` look like local scratch/runtime artifacts. Do not stage them unless you explicitly want them versioned.
- The large deletions under `docs/logs/`, `docs/models/`, and `docs/openclaw-analysis/` should be reviewed separately before committing. They may be intentional cleanup, but they are broad enough to deserve their own commit.
- Because the current branch is already `main`, there is no merge step here. The safest flow is grouped commits directly on `main`, or create a branch first and then cherry-pick these groups.

## Suggested Commit Order

### Commit 1

**Message**

```text
feat(dashboard): add fast monitoring parity and multi-model usage tracking
```

**Files**

```text
kabot/core/cost_tracker.py
kabot/gateway/handlers/_base.py
kabot/gateway/handlers/chat.py
kabot/gateway/handlers/config.py
kabot/gateway/handlers/dashboard.py
kabot/gateway/handlers/nodes.py
kabot/gateway/handlers/sessions.py
kabot/gateway/templates/dashboard.html
kabot/gateway/templates/sections/engine.html
kabot/gateway/templates/sections/overview.html
kabot/gateway/templates/sections/settings.html
kabot/gateway/webhook_server.py
tests/core/test_cost_tracker.py
tests/cli/test_gateway_dashboard_helpers.py
tests/gateway/test_webhooks_cases/
```

### Commit 2

**Message**

```text
feat(agent): improve multilingual speed, temporal replies, and filesystem followups
```

**Files**

```text
kabot/agent/context.py
kabot/agent/loop_core/tool_enforcement.py
kabot/agent/router.py
kabot/agent/semantic_intent.py
kabot/agent/tools/filesystem.py
kabot/memory/__init__.py
kabot/memory/memory_factory.py
kabot/memory/lazy_probe_memory.py
kabot/utils/text_safety.py
kabot/cli/agent_smoke_matrix.py
kabot/cli/commands_agent_command.py
kabot/cli/commands_system.py
tests/agent/test_router.py
tests/agent/test_semantic_intent.py
tests/agent/tools/test_filesystem.py
tests/cli/test_agent_runtime_config.py
tests/cli/test_agent_skill_runtime.py
tests/cli/test_agent_smoke_matrix.py
tests/cli/test_doctor_commands.py
tests/memory/test_memory_factory_lazy.py
tests/utils/test_text_safety.py
```

### Commit 3

**Message**

```text
refactor(cli): split commands and wizard helpers into focused modules
```

**Files**

```text
kabot/cli/commands.py
kabot/cli/commands_approvals.py
kabot/cli/commands_gateway.py
kabot/cli/commands_models_auth.py
kabot/cli/commands_provider_runtime.py
kabot/cli/commands_setup.py
kabot/cli/dashboard_payloads.py
kabot/cli/wizard/sections/channels.py
kabot/cli/wizard/sections/channels_helpers.py
kabot/cli/wizard/sections/model_auth.py
kabot/cli/wizard/sections/model_auth_helpers.py
kabot/cli/wizard/sections/tools_gateway_skills.py
kabot/cli/wizard/sections/tools_gateway_skills_helpers.py
tests/cli/test_commands_module_exports.py
tests/cli/test_dashboard_payloads_module.py
tests/cli/test_wizard_section_module_exports.py
```

### Commit 4

**Message**

```text
refactor(agent): split loop, runtime, parser, and matcher internals into packages
```

**Files**

```text
kabot/agent/cron_fallback_nlp.py
kabot/agent/cron_fallback_parts/
kabot/agent/loop.py
kabot/agent/loop_parts/
kabot/agent/loop_core/execution_runtime.py
kabot/agent/loop_core/execution_runtime_parts/
kabot/agent/loop_core/message_runtime.py
kabot/agent/loop_core/message_runtime_parts/
kabot/agent/skills.py
kabot/agent/skills_matching.py
kabot/agent/skills_parts/
kabot/agent/tools/stock.py
kabot/agent/tools/stock_matching.py
tests/agent/test_context_builder.py
tests/agent/test_cron_fallback_refactor_modules.py
tests/agent/test_loop_refactor_modules.py
tests/agent/test_refactor_module_exports.py
tests/agent/test_skills_entries_semantics.py
tests/agent/test_skills_matching.py
tests/agent/tools/test_stock_extractors.py
```

### Commit 5

**Message**

```text
test(refactor): split oversized runtime and gateway suites into themed files
```

**Files**

```text
tests/agent/loop_core/test_execution_runtime.py
tests/agent/loop_core/test_execution_runtime_cases/
tests/agent/loop_core/test_execution_runtime_refactor_modules.py
tests/agent/loop_core/test_message_runtime.py
tests/agent/loop_core/test_message_runtime_cases/
tests/agent/loop_core/test_message_runtime_refactor_modules.py
tests/agent/test_tool_enforcement.py
tests/agent/test_tool_enforcement_cases/
tests/agent/tools/test_stock.py
tests/gateway/test_webhooks.py
tests/gateway/test_webhooks_cases/
```

### Commit 6

**Message**

```text
docs: update changelog, smoke-agent docs, and refactor notes
```

**Files**

```text
CHANGELOG.md
HOW_TO_USE.MD
README.md
docs/plans/2026-03-09-*.md
```

### Commit 7

**Message**

```text
docs: remove stale implementation logs and openclaw analysis notes
```

**Files**

```text
docs/logs/
docs/models/overview.md
docs/openclaw-analysis/
```

**Use only if those deletions are intentional.**
