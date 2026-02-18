# Setup Wizard Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix critical setup wizard issues and add essential missing features

**Architecture:** Sequential Phase Approach - fix blocking issues first, then add core functionality

**Tech Stack:** Python, PowerShell, Bash, systemd, JSON state management

---

## Phase 1: Critical Fixes

### Task 1: Remove Duplicate Method Definition

**Files:**
- Modify: `kabot/cli/setup_wizard.py:362-379`

**Step 1: Remove incomplete duplicate method**

Delete lines 362-379 (incomplete `_configure_skills` method):
```python
# DELETE THESE LINES (362-379)
def _configure_skills(self):
    ClackUI.section_start("Skills")
    from kabot.agent.skills import SkillsLoader
    loader = SkillsLoader(self.config.workspace_path)

    skills = loader.list_skills(filter_unavailable=False)
    eligible = len([s for s in skills if s['valid']])

    console.print(f"│  Found {len(skills)} skills ({eligible} valid)")

    if not Confirm.ask("│  Configure skills config?", default=True):
        ClackUI.section_end()
        return

    for s in skills:
        name = s['name']
        meta = loader._get_skill_meta(name)
        requires = meta.get("requires", {})
```

**Step 2: Verify complete method remains**

Confirm complete method at lines 380-514 is intact and functional.

**Step 3: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "fix: remove duplicate _configure_skills method definition"
```

### Task 2: Fix Windows Service Installer

**Files:**
- Create: `deployment/install-kabot-service.ps1` (complete rewrite)

**Step 1: Create working PowerShell installer**

```powershell
# Windows Service Installer for Kabot
param(
    [string]$ServiceName = "KabotService",
    [string]$DisplayName = "Kabot AI Assistant Service",
    [string]$Description = "Kabot AI Assistant Background Service"
)

# Check admin privileges
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script requires Administrator privileges"
    exit 1
}

# Set paths with proper environment variables
$pythonExe = "$env:USERPROFILE\.kabot\venv\Scripts\python.exe"
$kabotScript = "$env:USERPROFILE\.kabot\venv\Scripts\kabot.exe"
$workingDir = "$env:USERPROFILE\.kabot"
$logPath = "$env:USERPROFILE\.kabot\logs\service.log"

# Validate paths exist
if (-not (Test-Path $pythonExe)) {
    Write-Error "Python executable not found at: $pythonExe"
    exit 1
}

if (-not (Test-Path $kabotScript)) {
    Write-Error "Kabot executable not found at: $kabotScript"
    exit 1
}

# Create service
$servicePath = "`"$kabotScript`" daemon --log-file `"$logPath`""

try {
    New-Service -Name $ServiceName -BinaryPathName $servicePath -DisplayName $DisplayName -Description $Description -StartupType Automatic
    Write-Host "Service '$ServiceName' created successfully"

    # Start service
    Start-Service -Name $ServiceName
    Write-Host "Service '$ServiceName' started successfully"

} catch {
    Write-Error "Failed to create/start service: $_"
    exit 1
}
```

**Step 2: Test installer**

Run: `powershell -ExecutionPolicy Bypass -File deployment/install-kabot-service.ps1`
Expected: Service created and started successfully

**Step 3: Commit**

```bash
git add deployment/install-kabot-service.ps1
git commit -m "fix: rewrite Windows service installer with proper syntax"
```

### Task 3: Implement Linux Service Installer

**Files:**
- Create: `deployment/install-linux-service.sh`

**Step 1: Create systemd service installer**

```bash
#!/bin/bash
# Linux Service Installer for Kabot

set -e

SERVICE_NAME="kabot"
SERVICE_USER="${SUDO_USER:-$USER}"
KABOT_HOME="$HOME/.kabot"
KABOT_BIN="$KABOT_HOME/venv/bin/kabot"

# Check if kabot is installed
if [ ! -f "$KABOT_BIN" ]; then
    echo "Error: Kabot not found at $KABOT_BIN"
    exit 1
fi

# Create systemd service file
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Kabot AI Assistant Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$KABOT_HOME
ExecStart=$KABOT_BIN daemon
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "Service '$SERVICE_NAME' installed and started successfully"
echo "Status: $(sudo systemctl is-active $SERVICE_NAME)"
```

**Step 2: Test installer**

Run: `bash deployment/install-linux-service.sh`
Expected: Service installed and running

**Step 3: Commit**

```bash
git add deployment/install-linux-service.sh
git commit -m "feat: implement Linux systemd service installer"
```

### Task 4: Add API Key Validation

**Files:**
- Modify: `kabot/cli/setup_wizard.py` (add validation to auth section)

**Step 1: Create validation framework**

Add after line 500 in setup_wizard.py:
```python
def _validate_api_key(self, provider: str, api_key: str) -> bool:
    """Validate API key by making a test call."""
    if not api_key or api_key.strip() == "":
        return True  # Skip validation for empty keys

    try:
        if provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            client.models.list()
            return True
        elif provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        elif provider == "groq":
            import groq
            client = groq.Groq(api_key=api_key)
            client.models.list()
            return True
    except Exception as e:
        console.print(f"│  [red]Validation failed: {str(e)}[/red]")
        return False

    return True  # Default to valid for unknown providers
```

**Step 2: Integrate validation into auth flow**

Modify the auth configuration section to call validation before saving keys.

**Step 3: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat: add API key validation during setup"
```

## Phase 2: Core Features

### Task 5: Create Windows Uninstaller

**Files:**
- Create: `uninstall.ps1`

**Step 1: Create uninstall script**

```powershell
# Kabot Uninstaller for Windows
param(
    [switch]$KeepConfig,
    [switch]$DryRun
)

$ServiceName = "KabotService"
$InstallPath = "$env:USERPROFILE\.kabot"

if ($DryRun) {
    Write-Host "DRY RUN - Would perform these actions:"
}

# Stop and remove service
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    if ($DryRun) {
        Write-Host "- Stop and remove service: $ServiceName"
    } else {
        Stop-Service -Name $ServiceName -Force
        Remove-Service -Name $ServiceName
        Write-Host "Service removed"
    }
}

# Remove from PATH
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$kabotPath = "$InstallPath\venv\Scripts"
if ($userPath -like "*$kabotPath*") {
    if ($DryRun) {
        Write-Host "- Remove from PATH: $kabotPath"
    } else {
        $newPath = $userPath -replace [regex]::Escape(";$kabotPath"), ""
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Host "Removed from PATH"
    }
}

# Remove installation directory
if (Test-Path $InstallPath) {
    if (-not $KeepConfig) {
        if ($DryRun) {
            Write-Host "- Remove directory: $InstallPath"
        } else {
            Remove-Item -Path $InstallPath -Recurse -Force
            Write-Host "Installation directory removed"
        }
    } else {
        Write-Host "Keeping configuration as requested"
    }
}

if (-not $DryRun) {
    Write-Host "Kabot uninstalled successfully"
}
```

**Step 2: Test uninstaller**

Run: `powershell -ExecutionPolicy Bypass -File uninstall.ps1 -DryRun`
Expected: Shows what would be removed

**Step 3: Commit**

```bash
git add uninstall.ps1
git commit -m "feat: add Windows uninstaller script"
```

### Task 6: Create Linux/Mac Uninstaller

**Files:**
- Create: `uninstall.sh`

**Step 1: Create uninstall script**

```bash
#!/bin/bash
# Kabot Uninstaller for Linux/Mac

KEEP_CONFIG=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-config) KEEP_CONFIG=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

SERVICE_NAME="kabot"
INSTALL_PATH="$HOME/.kabot"
BIN_PATH="$HOME/.local/bin/kabot"

if [ "$DRY_RUN" = true ]; then
    echo "DRY RUN - Would perform these actions:"
fi

# Remove systemd service
if systemctl --user is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
    if [ "$DRY_RUN" = true ]; then
        echo "- Stop and disable service: $SERVICE_NAME"
    else
        systemctl --user stop "$SERVICE_NAME"
        systemctl --user disable "$SERVICE_NAME"
        sudo rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        sudo systemctl daemon-reload
        echo "Service removed"
    fi
fi

# Remove binary symlink
if [ -L "$BIN_PATH" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo "- Remove binary: $BIN_PATH"
    else
        rm "$BIN_PATH"
        echo "Binary removed"
    fi
fi

# Remove installation directory
if [ -d "$INSTALL_PATH" ]; then
    if [ "$KEEP_CONFIG" = false ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "- Remove directory: $INSTALL_PATH"
        else
            rm -rf "$INSTALL_PATH"
            echo "Installation directory removed"
        fi
    else
        echo "Keeping configuration as requested"
    fi
fi

if [ "$DRY_RUN" = false ]; then
    echo "Kabot uninstalled successfully"
fi
```

**Step 2: Test uninstaller**

Run: `bash uninstall.sh --dry-run`
Expected: Shows what would be removed

**Step 3: Commit**

```bash
git add uninstall.sh
git commit -m "feat: add Linux/Mac uninstaller script"
```

### Task 7: Implement Configuration Backup

**Files:**
- Modify: `kabot/cli/setup_wizard.py` (add backup system)

**Step 1: Add backup functionality**

```python
def _create_backup(self) -> str:
    """Create configuration backup before changes."""
    import shutil
    from datetime import datetime

    backup_dir = Path.home() / ".kabot" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_path = backup_dir / f"{timestamp}_pre-setup"
    backup_path.mkdir(exist_ok=True)

    config_file = Path.home() / ".kabot" / "config.json"
    if config_file.exists():
        shutil.copy2(config_file, backup_path / "config.json")

        # Create metadata
        metadata = {
            "created_at": timestamp,
            "type": "pre-setup",
            "original_path": str(config_file)
        }

        with open(backup_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        # Create checksum
        import hashlib
        with open(backup_path / "config.json", "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        with open(backup_path / "checksum.sha256", "w") as f:
            f.write(f"{checksum}  config.json\n")

    return str(backup_path)
```

**Step 2: Integrate backup into setup flow**

Call `_create_backup()` at the start of setup process.

**Step 3: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat: add configuration backup system"
```

### Task 8: Add Setup State Persistence

**Files:**
- Modify: `kabot/cli/setup_wizard.py` (add state tracking)

**Step 1: Add state management**

```python
def _load_setup_state(self) -> dict:
    """Load setup state from file."""
    state_file = Path.home() / ".kabot" / "setup-state.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {
        "version": "1.0",
        "started_at": None,
        "sections": {},
        "user_selections": {}
    }

def _save_setup_state(self, section: str, completed: bool = False, **data):
    """Save setup state to file."""
    state_file = Path.home() / ".kabot" / "setup-state.json"
    state = self._load_setup_state()

    if not state["started_at"]:
        state["started_at"] = datetime.now().isoformat()

    state["last_updated"] = datetime.now().isoformat()
    state["sections"][section] = {
        "completed": completed,
        "timestamp": datetime.now().isoformat(),
        **data
    }

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

def _clear_setup_state(self):
    """Clear setup state file on successful completion."""
    state_file = Path.home() / ".kabot" / "setup-state.json"
    if state_file.exists():
        state_file.unlink()
```

**Step 2: Add resume capability**

Add resume detection at start of setup process.

**Step 3: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "feat: add setup state persistence and resume capability"
```

### Task 9: Fix Built-in Skills Installation

**Files:**
- Modify: `kabot/cli/setup_wizard.py` (integrate skills installation)

**Step 1: Call skills installation in setup flow**

Add call to `_install_builtin_skills()` in the main setup flow after skills configuration.

**Step 2: Add progress indicators**

Enhance skills installation with progress feedback.

**Step 3: Commit**

```bash
git add kabot/cli/setup_wizard.py
git commit -m "fix: integrate built-in skills installation into setup flow"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-02-18-setup-wizard-fixes-implementation.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?