# Native Google Without npm Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Kabot's Google integrations native-first and production-ready without requiring npm as part of the core Google feature path.

**Architecture:** Keep Google inside Kabot's Python tool/runtime model, harden auth and account management, then expand native feature coverage to Sheets and Contacts before considering any optional external backend adapters.

**Tech Stack:** Python, asyncio, Google API Python client libraries, Kabot runtime/tool registry, pytest, setup wizard, doctor diagnostics.

---

### Task 1: Define native Google strategy in docs and cross-link the gap audit

**Files:**
- Create: `docs/plans/2026-03-07-native-google-no-npm-design.md`
- Modify: `docs/plans/2026-03-07-google-native-vs-gogcli-gap-matrix.md`

**Step 1: Write the design document**

Include:
- native-first decision
- no-npm requirement
- role of optional external backends
- feature roadmap priorities

**Step 2: Cross-link the gap matrix**

Add a short section or note that this design is the preferred direction derived from the gap matrix.

**Step 3: Verify docs render cleanly**

Run:

```powershell
Get-Content docs/plans/2026-03-07-native-google-no-npm-design.md -TotalCount 40
```

Expected:
- file exists
- title and sections are present

**Step 4: Commit**

```bash
git add docs/plans/2026-03-07-native-google-no-npm-design.md docs/plans/2026-03-07-google-native-vs-gogcli-gap-matrix.md
git commit -m "docs: define native google no-npm direction"
```

### Task 2: Introduce a native Google account profile model

**Files:**
- Modify: `kabot/auth/google_auth.py`
- Modify: `kabot/config/schema.py`
- Modify: `kabot/config/loader.py`
- Modify: `kabot/cli/commands.py`
- Modify: `kabot/cli/wizard/sections/core.py`
- Test: `tests/config/test_loader_meta_migration.py`
- Test: `tests/cli/test_setup_wizard_tools_menu.py`

**Step 1: Write the failing config tests**

Add tests for:
- default single-profile compatibility
- multiple Google account profile entries
- backwards compatibility with current `google_credentials.json` / `google_token.json`

**Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/config/test_loader_meta_migration.py -v
```

Expected:
- FAIL because Google account profile schema does not exist yet

**Step 3: Implement profile-aware auth storage**

Target behavior:
- support a default account profile
- support named profiles
- keep current single-account path working

**Step 4: Add CLI/wizard selection surface**

Support:
- default profile selection
- adding or replacing profile credentials
- showing active Google profile

**Step 5: Run tests**

Run:

```bash
pytest tests/config/test_loader_meta_migration.py tests/cli/test_setup_wizard_tools_menu.py -v
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add kabot/auth/google_auth.py kabot/config/schema.py kabot/config/loader.py kabot/cli/commands.py kabot/cli/wizard/sections/core.py tests/config/test_loader_meta_migration.py tests/cli/test_setup_wizard_tools_menu.py
git commit -m "feat: add native google account profile model"
```

### Task 3: Replace plain token-file storage with a safer native storage abstraction

**Files:**
- Modify: `kabot/auth/google_auth.py`
- Create: `kabot/auth/google_token_store.py`
- Test: `tests/agent/tools/test_google_suite.py`
- Test: `tests/cli/test_doctor_commands.py`

**Step 1: Write failing tests**

Cover:
- default file-backed mode still works
- secure backend can be selected
- missing backend state yields actionable error

**Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/agent/tools/test_google_suite.py tests/cli/test_doctor_commands.py -v
```

Expected:
- FAIL because token storage abstraction does not exist

**Step 3: Implement storage abstraction**

Support:
- default file-backed mode for compatibility
- future secure backend selection
- profile-aware token lookup

**Step 4: Add doctor visibility**

Doctor should report:
- credentials present/missing
- token backend mode
- default profile

**Step 5: Run tests**

Run:

```bash
pytest tests/agent/tools/test_google_suite.py tests/cli/test_doctor_commands.py -v
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add kabot/auth/google_auth.py kabot/auth/google_token_store.py tests/agent/tools/test_google_suite.py tests/cli/test_doctor_commands.py
git commit -m "refactor: harden native google token storage"
```

### Task 4: Add manual/headless native Google auth flow

**Files:**
- Modify: `kabot/auth/google_auth.py`
- Modify: `kabot/cli/commands.py`
- Modify: `kabot/cli/wizard/sections/core.py`
- Test: `tests/cli/test_agent_cron_unavailable.py`
- Create: `tests/cli/test_google_auth_flow.py`

**Step 1: Write failing tests**

Cover:
- interactive browser flow
- manual copy/paste flow
- non-interactive mode gives a clear setup message

**Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/cli/test_google_auth_flow.py -v
```

Expected:
- FAIL because manual/headless mode does not exist

**Step 3: Implement minimal manual mode**

Support:
- print auth URL
- user pastes redirected URL/code
- validate and store token

**Step 4: Surface it in CLI and wizard**

Commands should explain:
- when browser auth is suitable
- when manual mode should be used

**Step 5: Run tests**

Run:

```bash
pytest tests/cli/test_google_auth_flow.py tests/cli/test_agent_cron_unavailable.py -v
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add kabot/auth/google_auth.py kabot/cli/commands.py kabot/cli/wizard/sections/core.py tests/cli/test_google_auth_flow.py tests/cli/test_agent_cron_unavailable.py
git commit -m "feat: add headless native google auth flow"
```

### Task 5: Add native Google Sheets support

**Files:**
- Create: `kabot/integrations/google_sheets.py`
- Modify: `kabot/agent/tools/google_suite.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/tools/test_google_suite.py`

**Step 1: Write failing tests**

Cover:
- get range
- update range
- append rows
- metadata fetch

**Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/agent/tools/test_google_suite.py -k "sheets" -v
```

Expected:
- FAIL because native Sheets tool/client does not exist

**Step 3: Implement minimal client**

Support:
- `get_values`
- `update_values`
- `append_values`
- `metadata`

**Step 4: Register Sheets as a runtime tool**

Add a structured `google_sheets` tool to optional tool loading.

**Step 5: Run tests**

Run:

```bash
pytest tests/agent/tools/test_google_suite.py -k "sheets" -v
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add kabot/integrations/google_sheets.py kabot/agent/tools/google_suite.py kabot/agent/loop.py tests/agent/tools/test_google_suite.py
git commit -m "feat: add native google sheets tool"
```

### Task 6: Add native Google Contacts support

**Files:**
- Create: `kabot/integrations/google_contacts.py`
- Modify: `kabot/agent/tools/google_suite.py`
- Modify: `kabot/agent/loop.py`
- Test: `tests/agent/tools/test_google_suite.py`

**Step 1: Write failing tests**

Cover:
- search contacts
- create contact
- update contact
- list directory/other contacts if supported by granted scopes

**Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/agent/tools/test_google_suite.py -k "contacts" -v
```

Expected:
- FAIL because native Contacts tool/client does not exist

**Step 3: Implement minimal client**

Support:
- search/list contacts
- create contact
- update contact

**Step 4: Register Contacts as a runtime tool**

Add a structured `google_contacts` tool to optional tool loading.

**Step 5: Run tests**

Run:

```bash
pytest tests/agent/tools/test_google_suite.py -k "contacts" -v
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add kabot/integrations/google_contacts.py kabot/agent/tools/google_suite.py kabot/agent/loop.py tests/agent/tools/test_google_suite.py
git commit -m "feat: add native google contacts tool"
```

### Task 7: Add native Google diagnostics to doctor and setup wizard

**Files:**
- Modify: `kabot/utils/doctor.py`
- Modify: `kabot/cli/wizard/sections/core.py`
- Modify: `README.md`
- Test: `tests/utils/test_doctor_matrix.py`
- Test: `tests/cli/test_setup_wizard_tools_menu.py`

**Step 1: Write failing tests**

Cover:
- doctor reports native Google readiness
- wizard shows Google profile/auth status
- docs mention no-npm native Google path

**Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/utils/test_doctor_matrix.py tests/cli/test_setup_wizard_tools_menu.py -v
```

Expected:
- FAIL because diagnostics are incomplete

**Step 3: Implement doctor/wizard reporting**

Report:
- credentials status
- token backend mode
- default account profile
- native services available
- missing scopes/capabilities where applicable

**Step 4: Update README**

Document:
- native-first Google setup
- no-npm requirement
- optional external backends are advanced only

**Step 5: Run tests**

Run:

```bash
pytest tests/utils/test_doctor_matrix.py tests/cli/test_setup_wizard_tools_menu.py -v
```

Expected:
- PASS

**Step 6: Commit**

```bash
git add kabot/utils/doctor.py kabot/cli/wizard/sections/core.py README.md tests/utils/test_doctor_matrix.py tests/cli/test_setup_wizard_tools_menu.py
git commit -m "docs: surface native google no-npm diagnostics"
```

### Task 8: Make `gogcli` optional and explicitly secondary

**Files:**
- Modify: `docs/plans/2026-03-07-google-native-vs-gogcli-gap-matrix.md`
- Modify: `docs/skill-system.md`
- Modify: `README.md`

**Step 1: Update docs wording**

Ensure all docs consistently state:
- native Google is the default path
- `gogcli` is optional
- npm is not required for Google support

**Step 2: Verify docs**

Run:

```powershell
Get-Content README.md -TotalCount 120
Get-Content docs/skill-system.md -TotalCount 120
```

Expected:
- wording is aligned

**Step 3: Commit**

```bash
git add README.md docs/skill-system.md docs/plans/2026-03-07-google-native-vs-gogcli-gap-matrix.md
git commit -m "docs: mark gogcli as optional google backend"
```

Plan complete and saved to `docs/plans/2026-03-07-native-google-no-npm-implementation.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
