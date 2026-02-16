# Design & Implementation Plan: Kabot v2.1 (Maturity Phase)

**Goal:** Achieve full architectural and visual parity with OpenClaw by implementing multi-agent isolation, a pro-active diagnostic engine (`doctor`), and a high-fidelity TUI.

---

## 🏗️ 1. Modern Architecture (Multi-Agent Home)

We are moving from a flat structure to a hierarchical one. This prevents memory contamination and allows specialized agents.

### 1.1 Folder Structure
```text
~/.kabot/
├── global_config.json      # Shared API keys (The Token Sink)
└── agents/
    └── main/               # Default agent ID
        ├── agent_config.json # Specific instructions/model for this agent
        ├── sessions/       # Chat history (SQLite)
        └── memory/         # Vector DB (ChromaDB)
```

### 1.2 Configuration Mapping
The `Config` object will now distinguish between:
- **Global Settings**: OAuth Tokens, API Keys, Gateway Port.
- **Agent Settings**: Primary Model, System Prompts, Workspace Path.

---

## 🛠️ 2. The Diagnostic Engine (`kabot doctor`)

A hybrid system that runs standalone or as a summary during status checks.

### 2.1 Component: `IntegrityChecker`
Checks the filesystem and environment.
```python
class IntegrityChecker:
    def check_folders(self):
        # Verify ~/.kabot/agents/main exists
        pass
    def check_binary(self, name):
        # Verify shutil.which(name)
        pass
```

### 2.2 Component: `AuthProber`
Pings providers to verify keys without starting a full session.
```python
async def probe_openai(api_key):
    # GET https://api.openai.com/v1/models with headers
    pass
```

---

## 🎨 3. Visual Parity (Clack-Style TUI)

Implementing a UI library inside `kabot/cli/setup_wizard.py` to handle the OpenClaw aesthetic.

### 3.1 UI Toolkit Code Example
```python
def draw_clack_box(title, content, style="dim"):
    panel = Panel(
        content,
        title=f" {title} ",
        title_align="left",
        border_style=style,
        box=box.ROUNDED
    )
    console.print("│")
    console.print(f"◇  {panel}")
```

---

## 📅 4. Implementation Phases

### Phase 1: Migration & Multi-Agent Logic
- [ ] **Task 1.1**: Update `kabot/config/loader.py` to handle `agents/` subdirectories.
- [ ] **Task 1.2**: Create a migration script to move existing `sessions/` and `memory/` into `agents/main/`.
- [ ] **Task 1.3**: Update `AgentLoop` to accept an `agent_id` parameter.

### Phase 2: Diagnostic Suite (`kabot doctor`)
- [ ] **Task 2.1**: Implement `kabot/utils/doctor.py` with all health checks.
- [ ] **Task 2.2**: Add `kabot doctor` command to `cli/commands.py`.
- [ ] **Task 2.3**: Integrate "Health Summary" into the top of `kabot status`.

### Phase 3: Skill Eligibility & Tool Audit
- [ ] **Task 3.1**: Add `check_requirements()` method to all Tool classes.
- [ ] **Task 3.2**: Update `models list` to show "Missing Requirements" for specific skills.

### Phase 4: Final TUI Polish
- [ ] **Task 4.1**: Refactor `setup_wizard.py` to use the vertical line (`│`) and boxed summary patterns.
- [ ] **Task 4.2**: Add real-time port probing to the main menu.

---

## 🧪 5. Verification & Success Criteria

1.  **Isolation Test**: Create agent `work` and agent `personal`. Verify `work` cannot see `personal` memory.
2.  **Doctor Test**: Delete `sessions/` folder. Verify `kabot doctor` reports a **CRITICAL** error.
3.  **Probing Test**: Change OpenAI key to an invalid one. Verify `kabot status` marks it as **FAILED**.
