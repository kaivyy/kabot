# Setup Wizard Maintainability Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce maintenance cost in `kabot/cli/setup_wizard.py` by extracting reusable wizard UI and channel menu composition into dedicated modules while keeping runtime behavior intact.

**Architecture:** Keep `SetupWizard` as flow orchestrator, but move terminal UI primitives (`ClackUI`) and channel menu option construction into `kabot/cli/wizard/` modules. This decreases file size/coupling and makes UI behavior testable with focused unit tests.

**Tech Stack:** Python 3.13, questionary, rich, pytest.

---

### Task 1: Add failing tests for extracted wizard UI and channel menu composition

**Files:**
- Create: `tests/cli/test_wizard_modules.py`

**Step 1: Write the failing test**

```python
from kabot.cli.wizard.ui import ClackUI
from kabot.cli.wizard.channel_menu import build_channel_menu_options
```

```python
def test_channel_menu_options_render_plain_status_labels():
    wizard = SetupWizard()
    wizard.config.channels.telegram.enabled = True
    options = build_channel_menu_options(wizard.config.channels)
    titles = [choice.title for choice in options]
    assert any("Telegram" in title and "ENABLED" in title for title in titles)
```

**Step 2: Run test to verify it fails**

Run:
```bash
pytest tests/cli/test_wizard_modules.py -q
```
Expected: FAIL due missing `kabot.cli.wizard` module/helpers.

**Step 3: Keep implementation unchanged**

```python
# No production change in Task 1
```

**Step 4: Re-run test (still failing)**

Run:
```bash
pytest tests/cli/test_wizard_modules.py -q
```
Expected: FAIL remains until implementation exists.

---

### Task 2: Extract wizard UI primitives into dedicated module

**Files:**
- Create: `kabot/cli/wizard/__init__.py`
- Create: `kabot/cli/wizard/ui.py`
- Modify: `kabot/cli/setup_wizard.py`

**Step 1: Confirm failing test scope still focused**

Run:
```bash
pytest tests/cli/test_wizard_modules.py -q
```
Expected: FAIL (import errors).

**Step 2: Implement minimal module extraction**

```python
# ui.py
class ClackUI:
    ...
```

```python
# setup_wizard.py
from kabot.cli.wizard.ui import ClackUI
```

**Step 3: Run test to verify import/test progress**

Run:
```bash
pytest tests/cli/test_wizard_modules.py -q
```
Expected: PARTIAL PASS/FAIL (channel menu helper not yet implemented).

---

### Task 3: Extract channel menu option builder and wire setup wizard

**Files:**
- Create: `kabot/cli/wizard/channel_menu.py`
- Modify: `kabot/cli/setup_wizard.py`
- Modify: `tests/cli/test_setup_wizard_channel_instances.py`

**Step 1: Add/adjust failing assertions first**

```python
assert all("[green]" not in title and "[dim]" not in title for title in titles)
```

**Step 2: Run tests to verify fail**

Run:
```bash
pytest tests/cli/test_wizard_modules.py tests/cli/test_setup_wizard_channel_instances.py -q
```
Expected: FAIL before helper wiring is complete.

**Step 3: Implement minimal channel menu composition helper**

```python
def build_channel_menu_options(channels_config):
    return [questionary.Choice(...), ...]
```

```python
# setup_wizard.py
options = build_channel_menu_options(c)
```

**Step 4: Run tests to verify pass**

Run:
```bash
pytest tests/cli/test_wizard_modules.py tests/cli/test_setup_wizard_channel_instances.py -q
```
Expected: PASS.

---

### Task 4: Update changelog and run regression verification

**Files:**
- Modify: `CHANGELOG.md`
- Verify: `kabot/cli/setup_wizard.py`

**Step 1: Add changelog entry under 0.5.7**

```markdown
### Changed
- Refactored setup wizard maintainability by extracting UI primitives and channel menu composition into dedicated modules.
```

**Step 2: Run targeted regression suite**

Run:
```bash
pytest tests/cli/test_setup_wizard_memory.py tests/cli/test_setup_wizard_channel_instances.py tests/cli/test_setup_wizard_ui_style.py tests/cli/test_wizard_modules.py -q
python -m py_compile kabot/cli/setup_wizard.py kabot/cli/wizard/ui.py kabot/cli/wizard/channel_menu.py
```
Expected: PASS.

**Step 3: Manual smoke check**

Run:
```bash
python -c "from kabot.cli.setup_wizard import ClackUI; print('ok', ClackUI.__name__)"
```
Expected: `ok ClackUI`.

