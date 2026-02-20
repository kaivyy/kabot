# Kabot Installation Script for Windows PowerShell
# Usage: .\install.bat

param(
    [string]$Version = "latest",
    [string]$InstallDir = "$env:USERPROFILE\.kabot"
)

$ErrorActionPreference = "Stop"

# Force UTF-8 for output
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Minimum Python version
$MinPythonVersion = [version]"3.11"

function Write-Info {
    param([string]$Message)
    Write-Host "==> " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "==> " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Error {
    param([string]$Message)
    Write-Host "==> ERROR: " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Find-Python {
    $pythonCommands = @("python", "python3", "py")

    foreach ($cmd in $pythonCommands) {
        try {
            $versionOutput = & $cmd --version 2>&1
            if ($versionOutput -match "Python (\d+\.\d+)") {
                $pyVersion = [version]$matches[1]
                if ($pyVersion -ge $MinPythonVersion) {
                    return $cmd
                }
            }
        }
        catch {
            continue
        }
    }

    return $null
}

function Get-InstallEnvironment {
    $isRemote = [bool]($env:SSH_CLIENT -or $env:SSH_TTY -or $env:CI)
    $isInteractive = [Environment]::UserInteractive
    $isHeadless = $isRemote -or (-not $isInteractive)

    $tags = @()
    if ($isRemote) { $tags += "vps" }
    if ($env:CI) { $tags += "ci" }
    if ($isHeadless) { $tags += "headless" }

    return @{
        IsRemote      = $isRemote
        IsHeadless    = $isHeadless
        IsInteractive = $isInteractive
        Tags          = $tags
    }
}

function Main {
    # Print Logo (Ultra-High Fidelity Gemini Shaded)
    $logo = @"
██╗  ██╗ █████╗ ██████╗  ██████╗ ████████╗
██║ ██╔╝██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝
█████╔╝ ███████║██████╔╝██║   ██║   ██║   
██╔═██╗ ██╔══██║██╔══██╗██║   ██║   ██║   
██║  ██╗██║  ██║██████╔╝╚██████╔╝   ██║   
╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝    ╚═╝   
"@
    Write-Host $logo -ForegroundColor Cyan

    Write-Info "Installing Kabot AI Agent..."
    $runtime = Get-InstallEnvironment
    if ($runtime.Tags.Count -gt 0) {
        Write-Info "Detected environment: windows ($($runtime.Tags -join ', '))"
    }
    else {
        Write-Info "Detected environment: windows"
    }

    # Check for Python
    Write-Info "Checking for Python >= $MinPythonVersion..."
    $pythonCmd = Find-Python

    if (-not $pythonCmd) {
        Write-Error "Python $MinPythonVersion or higher is required but not found."
        Write-Error "Please install Python from https://www.python.org/downloads/"
        Write-Error "During installation, make sure to check 'Add Python to PATH'"
        exit 1
    }

    $pythonVersion = & $pythonCmd --version
    Write-Info "Found $pythonVersion"

    # Create installation directory
    Write-Info "Creating installation directory at $InstallDir..."
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

    $venvDir = Join-Path $InstallDir "venv"
    $binDir = Join-Path $InstallDir "bin"
    New-Item -ItemType Directory -Force -Path $binDir | Out-Null

    # Create virtual environment
    Write-Info "Creating virtual environment..."
    if (Test-Path $venvDir) {
        Write-Warn "Virtual environment already exists. Removing old installation..."
        Remove-Item -Recurse -Force $venvDir
    }
    & $pythonCmd -m venv $venvDir

    # Activate virtual environment and install
    $venvPython = Join-Path $venvDir "Scripts\python.exe"
    $venvPip = Join-Path $venvDir "Scripts\pip.exe"

    # Upgrade pip using a safer method
    Write-Info "Upgrading pip..."
    & $venvPython -m pip install --upgrade pip setuptools wheel | Out-Null

    # Install Kabot from LOCAL source
    Write-Info "Installing kabot-ai and dependencies from local source..."
    & $venvPip install -e .
    & $venvPip install questionary

    # Create wrapper batch file
    Write-Info "Creating kabot command wrapper..."
    $wrapperPath = Join-Path $binDir "kabot.bat"
    @"
@echo off
"$venvPython" -m kabot %*
"@ | Out-File -FilePath $wrapperPath -Encoding ASCII

    # Add to PATH if not already there
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$binDir*") {
        Write-Info "Adding $binDir to PATH..."
        [Environment]::SetEnvironmentVariable("Path", "$binDir;$userPath", "User")
        $env:Path = "$binDir;$env:Path"
    }

    # Run doctor to ensure integrity
    Write-Info "Running system health check (doctor)..."
    & "$venvPython" -m kabot doctor --fix

    # Run setup wizard (TUI) when interactive
    if ($runtime.IsInteractive) {
        Write-Info "Launching interactive setup wizard..."
        & "$venvPython" -m kabot setup
    }
    else {
        Write-Warn "Non-interactive session detected. Skipping setup wizard."
        Write-Info "Run this after install: kabot setup"
    }

    Write-Host ""
    Write-Info "Installation complete!"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Login: kabot auth login"
    Write-Host "  2. Explore models: kabot models list"
    Write-Host "  3. Configure: kabot setup"
    Write-Host ""
    Write-Host "Documentation: https://github.com/kaivyy/kabot"
    Write-Host ""
    if ($runtime.IsInteractive) {
        Read-Host "Press Enter to exit..."
    }
}

try {
    Main
}
catch {
    Write-Error $_.Exception.Message
    Write-Host ""
    if ([Environment]::UserInteractive) {
        Read-Host "Press Enter to exit..."
    }
}
