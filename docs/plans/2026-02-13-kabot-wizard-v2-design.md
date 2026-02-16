# Design Doc: Kabot Modular Setup Wizard (v2.0)

**Date**: 2026-02-13
**Status**: Design / Detailed Spec
**Target**: `kabot setup` & `kabot onboard` commands

---

## 📋 1. Vision & Goals
The objective is to replace the current linear setup process with an interactive, modular, and visually professional TUI (Terminal User Interface) that provides real-time feedback about the user's environment.

### Key Goals:
- **Aesthetic Parity**: Match the "Clack" library look used by OpenClaw (`┌`, `│`, `└`, `◇`).
- **Non-Linear Configuration**: Allow users to jump directly to "Channels" without re-entering "Model" settings.
- **Environment Awareness**: Real-time probing of the Gateway port.
- **Dynamic Content**: Auto-calculate model counts per provider for the selection menu.

---

## 🏗️ 2. Visual Component Library

### 2.1 The Logo Header
A large, multi-line ASCII art logo using standard block characters, followed by a version and tagline string.

### 2.2 The "Summary Box"
A visually distinct panel that appears at the top of the wizard if an existing configuration is detected.
```text
┌  Existing config detected ──────────╮
│                                     │
│  Model: anthropic/claude-3-opus     │
│  Gateway: http://localhost:18790    │
│                                     │
├─────────────────────────────────────╯
```

### 2.3 Command Prefixes
- `◇`: Information / Prompt.
- `●`: Selected / Active item.
- `○`: Inactive / Selectable item.
- `◆`: Multi-select or Action item.

---

## ⚙️ 3. Technical Specifications

### 3.1 Probing Logic (`kabot/utils/network.py`)
```python
def probe_gateway(host="127.0.0.1", port=18790, timeout=0.5) -> bool:
    """Fast socket-based check for gateway reachability."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0
```

### 3.2 Tiered Model Discovery
The `ModelRegistry` will be extended to return counts:
- `get_provider_stats()` -> `{"openai": 24, "anthropic": 12, ...}`
- This will be used to render labels like `amazon-bedrock (72 models)`.

### 3.3 State Management
The wizard will maintain a `WizardState` object during the session to track which sections have been visited and modified before committing to `config.json`.

---

## 📅 4. Phased Implementation Roadmap

### Phase 1: Brand & Layout Foundation
- **UI Toolkit**: Create a `ClackUI` helper class in `setup_wizard.py` to handle consistent indenting and character prefixes.
- **Logo**: Implement the big ASCII start screen.
- **Summary**: Build the existing config detection and display logic.

### Phase 2: Section Discovery & Probing
- **Network Util**: Create `kabot/utils/network.py`.
- **Environment Prompt**: The first question ("Where will the Gateway run?") with live probe results.
- **Main Menu**: The modular selection list.

### Phase 3: The Advanced Model Picker
- **Provider Filter**: Group models by provider.
- **Selection UI**: Paginated list of models for high-count providers (like Bedrock).
- **Manual Input**: Fallback for entering custom LiteLLM IDs.

### Phase 4: Component Configuration
- **Web Tools Sub-wizard**: Individual toggles for Search, Browser, and Exec.
- **Gateway Sub-wizard**: Host/Port configuration with validation.
- **Channel Sub-wizard**: A loop to configure multiple chat platforms.

### Phase 5: Finalization & Polish
- **Skill Setup**: Integrate `kabot skills list` into the wizard.
- **Health Check**: Run a self-test after setup finishes.
- **Outro**: Professional completion message with "Next Steps".

---

## 🧪 5. Testing Plan
1.  **Visual Audit**: Ensure no line breaks or formatting issues across different terminal widths.
2.  **State Audit**: Verify that selecting a model doesn't erase existing channel settings.
3.  **Probing Test**: Run `kabot gateway` in a separate window and verify the wizard detects it live.
