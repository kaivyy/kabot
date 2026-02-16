# Implementation Plan: Kabot v2.2 (Self-Healing & Parity)

**Goal:** Implement pro-active system maintenance, automatic directory fixing, and high-fidelity CLI feedback matching the OpenClaw 2026.2.12 standard.

---

## 🏗️ 1. Logic & Architecture Alignment

### 1.1 The "Doctor-First" Philosophy
In OpenClaw, the `doctor` is the gatekeeper. We will implement:
- **`kabot doctor --fix`**: A mode that automatically resolves CRITICAL issues (missing dirs, broken DBs).
- **Auto-Doctoring**: Running a silent health check during `kabot setup` and `kabot gateway` startup.

### 1.2 Agent Hierarchy Hardening
- **Agent Root**: `~/.kabot/agents/<id>/`
- **Session Store**: `~/.kabot/agents/<id>/sessions/` (SQLite per agent)
- **Credential Sink**: `~/.kabot/credentials/` (Global OAuth/API keys)

---

## 📅 2. Phased Implementation Tasks

### Phase 1: Advanced Self-Healing (`kabot doctor --fix`)
**Files:** `kabot/utils/doctor.py`, `kabot/cli/commands.py`
- [ ] **Task 1.1**: Implement `fix_issue(item_id)` in `KabotDoctor`.
- [ ] **Task 1.2**: Update `render_report()` to handle interactive fix prompts.
- [ ] **Task 1.3**: Add `--fix` flag to the `doctor` CLI command.

### Phase 2: Professional CLI Experience
**Files:** `kabot/cli/commands.py`, `kabot/__init__.py`
- [ ] **Task 2.1**: Implement a randomized "Tagline System" (Witty quotes like OpenClaw).
- [ ] **Task 2.2**: Add "Examples" and "Next Steps" to the root `kabot --help` output.
- [ ] **Task 2.3**: Ensure TUI panels match the exact Clack width and padding.

### Phase 3: Installer & Migration Logic
**Files:** `install.ps1`, `install.sh`, `kabot/utils/migration.py`
- [ ] **Task 3.1**: Update installers to run `kabot doctor --fix` immediately after package install.
- [ ] **Task 3.2**: Refine the migration script to move legacy `~/.kabot/*.db` into `~/.kabot/agents/main/`.

### Phase 4: Integration Verification
- [ ] **Verification**: Run `rm -rf ~/.kabot/agents/main/sessions` and verify `kabot doctor --fix` restores it perfectly.
- [ ] **Verification**: Verify `kabot auth status` correctly identifies profiles stored in the new hierarchy.

---

## 🎨 3. UI Component Spec (The "OpenClaw" Look)

Every command header will now follow this pattern:
```text
🐈 Kabot 1.0.0 (rev-id) — <Random Witty Tagline>
<Big Gemini-Style Logo>
```

---

## 🧪 4. Success Criteria
- [ ] Installer finishes by displaying a successful "Doctor" report.
- [ ] `kabot doctor` identifies missing directories as "CRITICAL".
- [ ] All data paths are dynamically derived from the active `agent_id`.
