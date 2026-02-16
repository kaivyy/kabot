# Modular Setup Wizard (OpenClaw-Style) Implementation Plan

**Goal:** Transform Kabot's setup process into a modular, interactive TUI wizard with real-time environment probing and advanced model filtering.

---

## 🏗️ Architecture

1.  **UI Component Layer**: Custom wrappers around `rich` to emulate the "Clack" aesthetic (vertical lines, dots, and boxes).
2.  **Probing Engine**: Lightweight async check to see if the Gateway (Port 18790) is reachable.
3.  **Section Loop**: A state-machine based loop that allows users to jump between different configuration sections.
4.  **Tiered Model Picker**: A two-step selection process (Filter by Provider -> Select Model) with model counts.

---

## 📅 Implementation Phases

### Phase 1: Brand & Layout (The "Clack" Look)
**Files:** `kabot/cli/setup_wizard.py`
- [ ] Add ASCII Art logo.
- [ ] Implement `draw_box(content)` and `draw_divider()` using Clack-style characters (`┌`, `│`, `└`, `◇`).
- [ ] Create `summarize_config()` to show the active model and gateway status in a side-panel style box.

### Phase 2: The Probing Engine
**Files:** `kabot/utils/network.py` (New), `kabot/cli/setup_wizard.py`
- [ ] Implement `is_gateway_reachable(host, port)` using a short-timeout socket connection.
- [ ] Integrate probing into the main setup menu:
    - `● Local (reachable)` or `● Local (not detected)`.

### Phase 3: Modular Section Selection
**Files:** `kabot/cli/setup_wizard.py`
- [ ] Implement the `main_menu()` loop.
- [ ] Define sections:
    - **Workspace**: Path selection.
    - **Model**: Trigger Advanced Picker (Phase 4).
    - **Tools**: Toggle Web Search, Browser, Shell Exec.
    - **Gateway**: Configure Port, Host, and Bindings.
    - **Channels**: Individual sub-menus for TG, WhatsApp, etc.
- [ ] Add "Continue/Finish" option to save and exit.

### Phase 4: Advanced Model Picker
**Files:** `kabot/cli/setup_wizard.py`, `kabot/providers/registry.py`
- [ ] Implement `provider_filter_menu()`:
    - Shows list like: `anthropic (15 models)`, `openai (24 models)`, etc.
- [ ] Implement `model_selection_menu(provider_id)`:
    - Shows full list of models for that specific provider.
    - Includes `Keep current` and `Enter manually` options.

---

## 🧪 Success Criteria
- [ ] The setup wizard looks visually similar to the `openclaw config` screenshot.
- [ ] Probing correctly identifies if `kabot gateway` is running.
- [ ] User can configure "Channels" without having to re-configure "Model".
- [ ] Model aliases are correctly resolved during the selection process.
