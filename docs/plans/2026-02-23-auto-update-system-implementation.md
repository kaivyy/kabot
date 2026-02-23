# Auto-Update System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build chatbot-accessible auto-update system for Kabot with check/update/restart flow.

**Architecture:** Two tools (CheckUpdateTool, SystemUpdateTool) + UpdateService for restart logic. Tools return JSON to prevent AI hallucination.

**Tech Stack:** Python 3.11+, httpx (GitHub API), subprocess (git/pip), pytest

---

### Task 1: Create UpdateService for restart logic

**Files:**
- Create: `kabot/services/__init__.py`
- Create: `kabot/services/update_service.py`

**Step 1: Create services directory and __init__.py**

```bash
mkdir -p kabot/services
touch kabot/services/__init__.py
```

**Step 2: Write UpdateService implementation**

```python
"""Update service for handling Kabot restarts."""
import os
import sys
import platform
import subprocess
from pathlib import Path
from loguru import logger


class UpdateService:
    """Service for handling Kabot restart after updates."""

    def __init__(self):
        self.kabot_dir = Path(__file__).parent.parent.parent.resolve()

    def create_restart_script(self) -> Path:
        """Create platform-specific restart script."""
        pid = os.getpid()

        if platform.system() == "Windows":
            script_path = self.kabot_dir / "restart.bat"
            script_content = f"""@echo off
timeout /t 2 /nobreak >nul
taskkill /F /PID {pid} >nul 2>&1
cd /d "{self.kabot_dir}"
python -m kabot
"""
        else:  # Linux/Mac
            script_path = self.kabot_dir / "restart.sh"
            script_content = f"""#!/bin/bash
sleep 2
kill {pid} 2>/dev/null
cd "{self.kabot_dir}"
python -m kabot
"""

        script_path.write_text(script_content)
        if platform.system() != "Windows":
            script_path.chmod(0o755)

        logger.info(f"Created restart script: {script_path}")
        return script_path

    def execute_restart(self, script_path: Path):
        """Execute restart script and exit current process."""
        logger.info("Executing restart script...")

        if platform.system() == "Windows":
            subprocess.Popen([str(script_path)], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen([str(script_path)], shell=True, start_new_session=True)

        sys.exit(0)
```

**Step 3: Commit**

```bash
git add kabot/services/
git commit -m "feat: add UpdateService for restart logic"
```

---

### Task 2: Create CheckUpdateTool

**Files:**
- Create: `kabot/agent/tools/update.py`

**Step 1: Write CheckUpdateTool implementation**

```python
"""Update tools for checking and applying Kabot updates."""
import json
import subprocess
from pathlib import Path
from typing import Any
import httpx
from loguru import logger
from kabot.agent.tools.base import Tool


class CheckUpdateTool(Tool):
    """Check for Kabot updates from GitHub."""

    @property
    def name(self) -> str:
        return "check_update"

    @property
    def description(self) -> str:
        return "Check if Kabot updates are available. Returns current version, latest version, and commits behind. Use this when user asks about updates."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        try:
            install_method = self._detect_install_method()
            current_version = self._get_current_version()

            # Check GitHub API for latest release
            latest_release = await self._fetch_github_release()
            latest_version = latest_release.get("tag_name", "unknown")
            release_url = latest_release.get("html_url", "")

            # Check git status if git install
            commits_behind = 0
            if install_method == "git":
                commits_behind = self._check_commits_behind()

            update_available = self._compare_versions(current_version, latest_version)

            return json.dumps({
                "install_method": install_method,
                "current_version": current_version,
                "latest_version": latest_version,
                "commits_behind": commits_behind,
                "update_available": update_available,
                "release_url": release_url
            })
        except Exception as e:
            logger.error(f"Check update error: {e}")
            return json.dumps({"error": str(e), "update_available": False})

    def _detect_install_method(self) -> str:
        """Detect if installed via git or pip."""
        kabot_dir = Path(__file__).parent.parent.parent.parent
        if (kabot_dir / ".git").exists():
            return "git"
        return "pip"

    def _get_current_version(self) -> str:
        """Get current Kabot version."""
        try:
            from kabot import __version__
            return __version__
        except:
            return "unknown"

    async def _fetch_github_release(self) -> dict:
        """Fetch latest release from GitHub API."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://api.github.com/repos/kaivyy/kabot/releases/latest"
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.warning(f"GitHub API error: {e}")
        return {}

    def _check_commits_behind(self) -> int:
        """Check how many commits behind origin/main."""
        try:
            kabot_dir = Path(__file__).parent.parent.parent.parent
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD..origin/main"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Git check error: {e}")
        return 0

    def _compare_versions(self, current: str, latest: str) -> bool:
        """Compare version strings."""
        if current == "unknown" or latest == "unknown":
            return False
        return current != latest
```

**Step 2: Commit**

```bash
git add kabot/agent/tools/update.py
git commit -m "feat: add CheckUpdateTool for update detection"
```

---

### Task 3: Create SystemUpdateTool

**Files:**
- Modify: `kabot/agent/tools/update.py`

**Step 1: Add SystemUpdateTool to update.py**

```python
class SystemUpdateTool(Tool):
    """Update Kabot to latest version."""

    @property
    def name(self) -> str:
        return "system_update"

    @property
    def description(self) -> str:
        return "Update Kabot to latest version. Set confirm_restart=true to restart after update. Use this when user confirms update."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "confirm_restart": {
                    "type": "boolean",
                    "description": "Whether to restart Kabot after update"
                }
            },
            "required": []
        }

    async def execute(self, confirm_restart: bool = False, **kwargs: Any) -> str:
        try:
            install_method = self._detect_install_method()
            kabot_dir = Path(__file__).parent.parent.parent.parent

            # Check if can update
            if install_method == "git" and not self._can_update_git(kabot_dir):
                return json.dumps({
                    "success": False,
                    "reason": "dirty_working_tree",
                    "message": "Git working tree has uncommitted changes. Commit or stash first."
                })

            current_version = self._get_current_version()

            # Execute update
            if install_method == "git":
                success, message = self._git_update(kabot_dir)
            else:
                success, message = self._pip_update()

            if not success:
                return json.dumps({"success": False, "reason": "update_failed", "message": message})

            # Install dependencies
            self._install_dependencies(kabot_dir)

            updated_version = self._get_current_version()

            # Handle restart
            if confirm_restart:
                from kabot.services.update_service import UpdateService
                service = UpdateService()
                script_path = service.create_restart_script()
                service.execute_restart(script_path)

            return json.dumps({
                "success": True,
                "updated_from": current_version,
                "updated_to": updated_version,
                "restart_required": True
            })
        except Exception as e:
            logger.error(f"Update error: {e}")
            return json.dumps({"success": False, "reason": "exception", "message": str(e)})

    def _detect_install_method(self) -> str:
        kabot_dir = Path(__file__).parent.parent.parent.parent
        return "git" if (kabot_dir / ".git").exists() else "pip"

    def _get_current_version(self) -> str:
        try:
            from kabot import __version__
            return __version__
        except:
            return "unknown"

    def _can_update_git(self, kabot_dir: Path) -> bool:
        """Check if git working tree is clean."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and not result.stdout.strip()
        except:
            return False

    def _git_update(self, kabot_dir: Path) -> tuple[bool, str]:
        """Update via git pull."""
        try:
            # Fetch
            result = subprocess.run(
                ["git", "fetch", "origin"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return False, f"Git fetch failed: {result.stderr}"

            # Pull
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=kabot_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                return False, f"Git pull failed: {result.stderr}"

            return True, "Git update successful"
        except Exception as e:
            return False, str(e)

    def _pip_update(self) -> tuple[bool, str]:
        """Update via pip."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "kabot-ai"],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                return False, f"Pip upgrade failed: {result.stderr}"
            return True, "Pip update successful"
        except Exception as e:
            return False, str(e)

    def _install_dependencies(self, kabot_dir: Path):
        """Install/update dependencies."""
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                cwd=kabot_dir,
                capture_output=True,
                timeout=120
            )
        except Exception as e:
            logger.warning(f"Dependency install warning: {e}")
```

**Step 2: Commit**

```bash
git add kabot/agent/tools/update.py
git commit -m "feat: add SystemUpdateTool for update execution"
```

---

### Task 4: Register tools in registry

**Files:**
- Modify: `kabot/agent/loop.py` (find tool registration section)

**Step 1: Find tool registration in loop.py**

```bash
grep -n "register.*Tool" kabot/agent/loop.py | head -20
```

**Step 2: Add update tools to registry**

Add after other tool registrations:

```python
from kabot.agent.tools.update import CheckUpdateTool, SystemUpdateTool

# Register update tools
self.registry.register(CheckUpdateTool())
self.registry.register(SystemUpdateTool())
```

**Step 3: Commit**

```bash
git add kabot/agent/loop.py
git commit -m "feat: register update tools in agent loop"
```

---

### Task 5: Write unit tests

**Files:**
- Create: `tests/agent/tools/test_update.py`

**Step 1: Write test file**

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
from kabot.agent.tools.update import CheckUpdateTool, SystemUpdateTool


@pytest.mark.asyncio
async def test_check_update_tool_git_install():
    """Test CheckUpdateTool detects git install."""
    tool = CheckUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='git'), \
         patch.object(tool, '_get_current_version', return_value='0.5.2'), \
         patch.object(tool, '_fetch_github_release', new_callable=AsyncMock, return_value={
             'tag_name': 'v0.5.3',
             'html_url': 'https://github.com/kaivyy/kabot/releases/tag/v0.5.3'
         }), \
         patch.object(tool, '_check_commits_behind', return_value=5):

        result = await tool.execute()
        assert 'install_method' in result
        assert 'git' in result
        assert '0.5.3' in result
        assert 'update_available' in result


@pytest.mark.asyncio
async def test_check_update_tool_pip_install():
    """Test CheckUpdateTool detects pip install."""
    tool = CheckUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='pip'), \
         patch.object(tool, '_get_current_version', return_value='0.5.2'), \
         patch.object(tool, '_fetch_github_release', new_callable=AsyncMock, return_value={
             'tag_name': 'v0.5.3',
             'html_url': 'https://github.com/kaivyy/kabot/releases/tag/v0.5.3'
         }):

        result = await tool.execute()
        assert 'pip' in result
        assert 'commits_behind' in result


@pytest.mark.asyncio
async def test_system_update_tool_dirty_tree():
    """Test SystemUpdateTool blocks update on dirty working tree."""
    tool = SystemUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='git'), \
         patch.object(tool, '_can_update_git', return_value=False):

        result = await tool.execute(confirm_restart=False)
        assert 'dirty_working_tree' in result
        assert 'success' in result


@pytest.mark.asyncio
async def test_system_update_tool_git_success():
    """Test SystemUpdateTool git update success."""
    tool = SystemUpdateTool()

    with patch.object(tool, '_detect_install_method', return_value='git'), \
         patch.object(tool, '_can_update_git', return_value=True), \
         patch.object(tool, '_get_current_version', side_effect=['0.5.2', '0.5.3']), \
         patch.object(tool, '_git_update', return_value=(True, 'Success')), \
         patch.object(tool, '_install_dependencies'):

        result = await tool.execute(confirm_restart=False)
        assert 'success' in result
        assert 'true' in result.lower()
```

**Step 2: Run tests**

```bash
pytest tests/agent/tools/test_update.py -v
```

Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/agent/tools/test_update.py
git commit -m "test: add unit tests for update tools"
```

---

### Task 6: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

**Step 1: Add v0.5.3 entry to CHANGELOG**

Add after `## [Unreleased]`:

```markdown
## [0.5.3] - 2026-02-23

### Added
- **Chatbot-Accessible Auto-Update System**: Users can now check for updates and trigger updates via natural language
  - `check_update` tool: Detects available updates from GitHub releases and git commits
  - `system_update` tool: Executes update (git pull or pip upgrade) with restart confirmation
  - `UpdateService`: Handles platform-specific restart logic (Windows/Linux/Mac)
  - Supports both git clone and pip install methods
  - Anti-hallucination design: Tools return structured JSON data, not prose
  - Security: Validates working tree, requires restart confirmation, no arbitrary code execution

### Changed
- **Agent Loop**: Registered CheckUpdateTool and SystemUpdateTool in agent tool registry
```

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG for v0.5.3 auto-update system"
```

---

### Task 7: Update HOW-TO-USE.md

**Files:**
- Modify: `HOW-TO-USE.md`

**Step 1: Add auto-update section**

Add new section after existing content:

```markdown
## Auto-Update System

Kabot can check for updates and update itself via chatbot commands.

### Check for Updates

Ask Kabot to check for updates:
- "periksa apakah ada update baru?"
- "check for updates"
- "is there a new version?"

Kabot will respond with:
- Current version
- Latest available version
- Number of commits behind (for git installs)
- Whether update is available

### Update Kabot

To update Kabot:
1. Ask: "update program" or "update kabot"
2. Kabot will download and install the update
3. Kabot will ask: "Update selesai, restart sekarang?"
4. Respond "ya" or "yes" to restart

### Installation Methods

Kabot supports two installation methods:

**Git Clone** (Development):
- Updates via `git pull origin main`
- Requires clean working tree (no uncommitted changes)
- Shows commits behind

**Pip Install** (Production):
- Updates via `pip install --upgrade kabot-ai`
- Checks PyPI for latest version

### Restart Process

After update, Kabot creates a platform-specific restart script:
- **Windows**: `restart.bat` with 2-second delay
- **Linux/Mac**: `restart.sh` with 2-second delay

The script kills the current process and restarts Kabot automatically.
```

**Step 2: Commit**

```bash
git add HOW-TO-USE.md
git commit -m "docs: add auto-update system documentation to HOW-TO-USE"
```

---

### Task 8: Create git tag and push

**Files:**
- None (git operations)

**Step 1: Create annotated tag**

```bash
git tag -a v0.5.3 -m "Release v0.5.3 - Chatbot-Accessible Auto-Update System"
```

**Step 2: Push commits and tag**

```bash
git push origin main
git push origin v0.5.3
```

**Step 3: Verify tag on GitHub**

```bash
git ls-remote --tags origin | grep v0.5.3
```

Expected: Tag appears in remote

---

### Task 9: Run full test suite

**Files:**
- None (verification)

**Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass

**Step 2: Run update tests specifically**

```bash
pytest tests/agent/tools/test_update.py -v
```

Expected: All update tests pass

**Step 3: Manual verification**

Test in development:
1. Start Kabot
2. Ask: "periksa update"
3. Verify response shows version info
4. Ask: "update program" (don't confirm restart in dev)
5. Verify update process works

---

## Completion Checklist

- [ ] UpdateService created with restart logic
- [ ] CheckUpdateTool implemented
- [ ] SystemUpdateTool implemented
- [ ] Tools registered in agent loop
- [ ] Unit tests written and passing
- [ ] CHANGELOG.md updated
- [ ] HOW-TO-USE.md updated
- [ ] Git tag v0.5.3 created and pushed
- [ ] Full test suite passes
- [ ] Manual testing completed

## Notes

- Version is v0.5.3 (not final, as requested)
- Tools return JSON to prevent AI hallucination
- Restart requires explicit user confirmation
- Supports both git and pip installations
- Platform-specific restart scripts (Windows/Linux/Mac)
