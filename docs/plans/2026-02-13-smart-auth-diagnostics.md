# Comprehensive Smart Auth Diagnostics & Discovery Design

**Status**: Draft
**Date**: 2026-02-13
**Version**: 2.0
**Target**: Kabot Enhanced Authentication Layer

---

## 🏗️ 1. Architectural Overview

The goal is to create a "zero-configuration" experience for complex providers like Google Gemini CLI, where Kabot automatically finds or installs requirements and extracts hidden secrets from local source code.

### 1.1 Core Components
- **The Checker (`kabot/auth/diagnostics.py`)**: Responsible for pre-flight validation. It doesn't just check if a file exists; it checks if it's executable and returns the right version.
- **The Scout (`kabot/auth/discovery.py`)**: A tiered search engine. It starts with the most efficient search (PATH) and falls back to aggressive filesystem scanning if needed.
- **The Surgeon (`kabot/auth/extraction.py`)**: A new utility to parse non-standard credential files (JS, JSON, YAML) using Regex and AST parsing to pull out OAuth Client IDs.
- **The UI (`rich` integration)**: Beautiful, OpenClaw-style help boxes that provide actionable instructions.

---

## 📂 2. Technical Specification

### 2.1 Tiered Search Strategy
Discovery will follow this strict priority:
1.  **System PATH**: `shutil.which('gemini')`.
2.  **Environment Overrides**: Check `GEMINI_CLI_PATH`.
3.  **Heuristic Scan (Windows)**:
    - `%APPDATA%\npm\node_modules\@google\gemini-cli`
    - `%USERPROFILE%\.npm-global\node_modules\...`
4.  **Heuristic Scan (Unix)**:
    - `/usr/local/lib/node_modules/@google/gemini-cli`
    - `~/.npm-global/lib/node_modules/...`
5.  **User Prompt**: Final fallback if all else fails.

### 2.2 Extraction Regex
For `@google/gemini-cli`, we specifically target `oauth2.js`.
- **Client ID Pattern**: `r"(\d+-[a-z0-9]+\.apps\.googleusercontent\.com)"`
- **Client Secret Pattern**: `r"(GOCSPX-[A-Za-z0-9_-]+)"`

---

## 📅 3. Phased Implementation Tasks

### Phase 1: Diagnostic Foundation
- [ ] **Task 1.1**: Implement `DependencyStatus` dataclass.
- [ ] **Task 1.2**: Create `render_help_panel(tool_name, install_cmd, docs_url)` function.
- [ ] **Task 1.3**: Implement `GuidedInstaller` with support for:
    - `npm install -g @google/gemini-cli`
    - `brew install gemini-cli` (MacOS)

### Phase 2: Tiered Discovery Engine
- [ ] **Task 2.1**: Implement `find_node_module(module_name)` logic.
- [ ] **Task 2.2**: Implement `smart_path_resolver` that detects OS and picks search paths.
- [ ] **Task 2.3**: Create `ExtractionEngine` to read files safely without execution.

### Phase 3: Gemini CLI Specialist Handler
- [ ] **Task 3.1**: Create `GoogleGeminiCLIHandler`.
- [ ] **Task 3.2**: Implement `check_health()`:
    - If `gemini-cli` found -> Success.
    - If not found -> Trigger Phase 1 UI.
- [ ] **Task 3.3**: Implement `extract_secrets()`:
    - Find `oauth2.js` -> Regex search -> Return dict.
- [ ] **Task 3.4**: Launch `run_oauth_flow` on **Port 8085** (Gemini Standard).

### Phase 4: Integration & UX Polishing
- [ ] **Task 4.1**: Update `AuthManager` to support `pre_auth_hook()` for handlers.
- [ ] **Task 4.2**: Update `menu.py` to include the new provider method.
- [ ] **Task 4.3**: Final integration test on Windows and (simulated) VPS.

---

## 🛡️ 4. Edge Case Handling

| Scenario | Strategy |
| :--- | :--- |
| **Permission Denied** | Use `try-except` on file reads; notify user if sudo/admin is needed for auto-install. |
| **Old CLI Version** | Check `--version` and recommend `npm update` if patterns don't match. |
| **Port 8085 Occupied** | Use Kabot's existing auto-increment logic (8085 -> 8086). |
| **User Aborts Install** | Gracefully return to the main auth menu without crashing. |

---

## 🧪 5. Verification Plan

1.  **Unit Tests**: Mock `shutil.which` and `os.path.exists` to test all 5 search tiers.
2.  **Mock Extraction**: Create a fake `oauth2.js` and verify regex accuracy.
3.  **UI Verification**: Manually trigger the help panel to ensure formatting matches OpenClaw's aesthetic.
