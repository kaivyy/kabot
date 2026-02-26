# Auto-Update System Design

**Date**: 2026-02-23
**Status**: Approved
**Author**: Kabot AI

## Overview

Design chatbot-accessible auto-update system for Kabot that allows users to check for updates and trigger updates via natural language, similar to Kabot's update functionality but accessible through chat interface.

## Requirements

### Functional Requirements
1. **Check Updates**: User can ask "periksa apakah ada update baru?" and AI responds with accurate update status
2. **Update Execution**: User can say "update program" and system updates automatically
3. **Restart Confirmation**: After update, AI asks "restart sekarang?" and waits for user confirmation
4. **Non-Hallucinatory**: AI must not fake update information - all data comes from real sources
5. **Dual Install Support**: Support both git clone and pip install methods
6. **Hybrid Detection**: Check both GitHub releases and git commits for updates

### Non-Functional Requirements
1. **Security**: No arbitrary code execution, path validation, confirmation required for restart
2. **Reliability**: Graceful error handling, rollback safety, audit logging
3. **Performance**: GitHub API timeout 5s, total update timeout 5 minutes
4. **Testability**: Unit tests for all components, integration tests for full flow

## Architecture

### High-Level Design

```
User Chat â†’ AI Agent â†’ Tools â†’ Update Logic â†’ Git/PyPI â†’ Restart
                â†“
         Structured Data (no hallucination)
```

### Components

#### 1. CheckUpdateTool (`kabot/agent/tools/update.py`)

**Purpose**: Detect and report available updates without hallucination.

**Responsibilities**:
- Detect installation method (git vs pip)
- Check GitHub Releases API for latest version
- Check git status (commits behind, dirty state)
- Return structured JSON data

**Key Methods**:
```python
class CheckUpdateTool(Tool):
    name = "check_update"
    description = "Check if Kabot updates are available. Returns current version, latest version, and commits behind."

    async def execute(self) -> str:
        # 1. Detect install method
        install_method = self._detect_install_method()

        # 2. Get current version
        current_version = self._get_current_version(install_method)

        # 3. Check GitHub API for latest release
        latest_release = await self._fetch_github_release()

        # 4. Check git status (if git install)
        git_status = await self._check_git_status() if install_method == "git" else None

        # 5. Return structured data
        return json.dumps({
            "install_method": install_method,
            "current_version": current_version,
            "latest_version": latest_release["tag_name"],
            "commits_behind": git_status["behind"] if git_status else 0,
            "update_available": self._compare_versions(...),
            "release_url": latest_release["html_url"]
        })
```

**Anti-Hallucination Strategy**:
- Return JSON with concrete data (not prose)
- AI parses JSON to format response
- If API fails, return error in JSON (not fake data)
- Log all API calls for audit

#### 2. SystemUpdateTool (`kabot/agent/tools/update.py`)

**Purpose**: Execute update process with confirmation.

**Responsibilities**:
- Execute update based on install method
- Install dependencies
- Prepare restart (but don't execute yet)
- Return success/failure status

**Key Methods**:
```python
class SystemUpdateTool(Tool):
    name = "system_update"
    description = "Update Kabot to latest version. Set confirm_restart=true to restart after update."
    parameters = {
        "type": "object",
        "properties": {
            "confirm_restart": {
                "type": "boolean",
                "description": "Whether to restart Kabot after update"
            }
        },
        "required": []
    }

    async def execute(self, confirm_restart: bool = False) -> str:
        # 1. Pre-check: ensure no dirty state
        if not self._can_update():
            return json.dumps({"success": False, "reason": "dirty_working_tree"})

        # 2. Execute update
        if install_method == "git":
            result = await self._git_update()
        else:
            result = await self._pip_update()

        # 3. Install dependencies
        if result["success"]:
            await self._install_dependencies()

        # 4. Handle restart
        if confirm_restart:
            await self._trigger_restart()

        return json.dumps(result)
```

**Update Flow**:
- **Git**: `git fetch origin` â†’ `git pull origin main` â†’ `pip install -e .`
- **PyPI**: `pip install --upgrade kabot`
- **Dependencies**: `pip install -r requirements.txt` (if changed)

#### 3. UpdateService (`kabot/services/update_service.py`)

**Purpose**: Handle restart logic and process lifecycle.

**Responsibilities**:
- Create platform-specific restart scripts
- Execute restart with delay
- Manage process lifecycle

**Restart Strategy**:
```python
# Windows: Create .bat script
restart.bat:
  timeout /t 2
  taskkill /F /PID {pid}
  cd {kabot_dir}
  python -m kabot

# Linux: Create .sh script
restart.sh:
  sleep 2
  kill {pid}
  cd {kabot_dir}
  python -m kabot
```

**Key Methods**:
```python
class UpdateService:
    async def prepare_restart(self) -> str:
        # Create restart script
        script_path = self._create_restart_script()
        return script_path

    async def execute_restart(self, script_path: str):
        # Execute script in background
        subprocess.Popen([script_path], shell=True)
        # Exit current process
        sys.exit(0)
```

## Data Flow

### Update Check Flow

```
User: "periksa update"
  â†“
AI calls CheckUpdateTool.execute()
  â†“
Tool detects install method (git/pip)
  â†“
Tool fetches GitHub API (with timeout 5s)
  â†“
If git: check commits behind via git rev-list
  â†“
Return JSON: {install_method, current, latest, commits_behind, update_available}
  â†“
AI parses JSON and responds naturally
```

### Update Execution Flow

```
User: "update program"
  â†“
AI calls SystemUpdateTool.execute(confirm_restart=False)
  â†“
Tool validates: no dirty working tree, network available
  â†“
Execute update (git pull / pip upgrade)
  â†“
Install dependencies if requirements.txt changed
  â†“
Return JSON: {success, updated_from, updated_to, restart_required}
  â†“
AI asks: "Update selesai, restart sekarang?"
  â†“
User: "ya"
  â†“
AI calls SystemUpdateTool.execute(confirm_restart=True)
  â†“
Tool creates restart script and executes
  â†“
Process exits, restart script waits 2s, then restarts Kabot
```

## Error Handling

### Error Scenarios

1. **GitHub API Timeout**
   - Fallback to git commands only
   - Return partial data with warning

2. **Git Pull Conflict**
   - Return error with conflict details
   - Suggest manual resolution: `git stash` or `git reset --hard`

3. **Pip Upgrade Fails**
   - Return error with pip output
   - No automatic rollback (user can downgrade manually)

4. **Dirty Working Tree**
   - Block update
   - Tell user to commit/stash changes

5. **Network Unavailable**
   - Return clear error message
   - Suggest checking internet connection

6. **Restart Script Creation Fails**
   - Return error
   - Suggest manual restart

## Security & Anti-Hallucination

### Anti-Hallucination Measures

1. **Structured Output**: Tools return JSON, not prose
2. **API Verification**: GitHub API is source of truth for releases
3. **Git Verification**: Use `git rev-list` to count commits (not AI guess)
4. **Logging**: Log all API calls and git commands for audit
5. **No Fake Data**: If API fails, return error (not fake version)

### Security Measures

1. **No Arbitrary Code Execution**: Only run predefined commands
2. **Path Validation**: Validate kabot directory before operations
3. **Confirmation Required**: Restart requires explicit user confirmation
4. **Rollback Safety**: Don't auto-rollback (user controls via git)
5. **Rate Limiting**: Respect GitHub API rate limits (cache results)

## Testing Strategy

### Unit Tests (`tests/agent/tools/test_update.py`)

- Test install method detection (git vs pip)
- Test version comparison logic
- Test GitHub API parsing (with mocked responses)
- Test git command execution (with mocked subprocess)
- Test error handling for all failure modes

### Integration Tests

- Test full update flow in test environment
- Test restart script creation (don't execute)
- Test with real GitHub API (rate limit aware)

### Manual Testing

- Test on Windows and Linux
- Test git install update
- Test pip install update
- Test restart confirmation flow

## Implementation Plan

See `2026-02-23-auto-update-system-implementation.md` for detailed implementation steps.

## Deliverables

1. `kabot/agent/tools/update.py` - CheckUpdateTool and SystemUpdateTool
2. `kabot/services/update_service.py` - UpdateService for restart logic
3. `tests/agent/tools/test_update.py` - Unit tests
4. Updated `CHANGELOG.md` with new feature
5. Updated `HOW-TO-USE.md` with update instructions
6. Git tag for release (version TBD)

## Success Criteria

1. User can check updates via chat and get accurate information
2. User can trigger update via chat and system updates successfully
3. Restart confirmation works correctly
4. All tests pass
5. No hallucination - all data comes from real sources
6. Works on both Windows and Linux
7. Works for both git and pip installations


