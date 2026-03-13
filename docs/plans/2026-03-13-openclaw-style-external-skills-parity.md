# OpenClaw-Style External Skills Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot more skill-first like OpenClaw by supporting local external skill installs and preferring external skills over built-in stock/crypto tools when a matching skill exists.

**Architecture:** Extend the existing Kabot skill installer so it can import skills from local directories and packaged archives, then teach runtime routing to downrank built-in `stock`/`crypto` deterministic paths whenever a non-builtin matching skill is available. Keep built-in tools intact as fallback only.

**Tech Stack:** Python, Typer CLI, pytest, Kabot skill loader/runtime.

---

### Task 1: Add failing tests for local external skill installation

**Files:**
- Modify: `tests/cli/test_skill_repo_installer.py`
- Modify: `tests/cli/test_skills_commands.py`

**Step 1: Write failing tests**

Add coverage for:
- installing a skill from a local directory containing `SKILL.md`
- installing a skill from a packaged archive path
- CLI support for `kabot skills install --path ...`

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/cli/test_skill_repo_installer.py tests/cli/test_skills_commands.py -q
```

**Step 3: Implement minimal installer changes**

Add installer helpers for local source discovery and archive extraction without changing the git installer behavior.

**Step 4: Re-run tests**

Run the same pytest command and confirm green.

---

### Task 2: Add failing tests for external-skill-first routing

**Files:**
- Modify: `tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py`

**Step 1: Write failing tests**

Add coverage for:
- when an external managed/workspace skill matches a stock-style request, built-in `stock`/`crypto` should not be forced
- built-in tools still remain fallback when no external match exists

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q
```

**Step 3: Implement minimal routing changes**

Teach tool routing to consult the skill loader and suppress deterministic `stock`/`crypto` forcing when a non-builtin matching skill is available.

**Step 4: Re-run tests**

Run the same pytest command and confirm green.

---

### Task 3: Wire local install + precedence into CLI/runtime and document fallback behavior

**Files:**
- Modify: `kabot/cli/skill_repo_installer.py`
- Modify: `kabot/cli/commands_setup.py`
- Modify: `kabot/agent/skills.py`
- Modify: `kabot/agent/loop_core/tool_enforcement_parts/history_routing.py`
- Modify: `kabot/agent/loop_core/execution_runtime_parts/intent.py`
- Modify: `CHANGELOG.md`

**Step 1: Keep built-in stock/crypto tools as fallback**

Add comments/documentation that these tools are intentionally retained but de-prioritized when matching external skills are present.

**Step 2: Verify focused suite**

Run:
```bash
python -m pytest tests/cli/test_skill_repo_installer.py tests/cli/test_skills_commands.py tests/agent/test_tool_enforcement_cases/test_tool_enforcement_routing_and_aliases.py -q
```

**Step 3: Verify broader runtime slice**

Run:
```bash
python -m pytest tests/agent/loop_core/test_execution_runtime_cases/test_execution_runtime_tool_calls_and_skill_phases.py tests/agent/loop_core/test_message_runtime_cases/test_message_runtime_skill_workflows.py tests/cli/test_agent_skill_runtime.py -q
```

**Step 4: Update changelog**

Document:
- local external skill install support
- external-skill-first precedence over built-in stock/crypto fallback

