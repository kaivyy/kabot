# Kabot Installation Script for Windows PowerShell
# Usage: iwr -useb https://raw.githubusercontent.com/YOUR_ORG/kabot/master/install.ps1 | iex

param(
    [string]$Version = "latest",
    [string]$InstallDir = "$env:USERPROFILE\.kabot"
)

$ErrorActionPreference = "Stop"

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
        } catch {
            continue
        }
    }
    
    return $null
}

function Main {
    # Print Logo
    Write-Host "
  _  __     _           _
 | |/ /    | |         | |
 | ' / __ _| |__   ___ | |_
 |  < / _` | '_ \ / _ \| __|
 | . \ (_| | |_) | (_) | |_
 |_|\_\__,_|_.__/ \___/ \__|
" -ForegroundColor Cyan

    Write-Info "Installing Kabot AI Agent..."

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
    Write-Info "Found $pythonVersion at $(Get-Command $pythonCmd | Select-Object -ExpandProperty Source)"

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

    # Upgrade pip
    Write-Info "Upgrading pip..."
    & $venvPip install --upgrade pip setuptools wheel | Out-Null

    # Install Kabot
    Write-Info "Installing kabot-ai package..."
    if ($Version -eq "latest") {
        & $venvPip install kabot-ai
    } else {
        & $venvPip install "kabot-ai==$Version"
    }

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
        [Environment]::SetEnvironmentVariable(
            "Path",
            "$binDir;$userPath",
            "User"
        )
        $env:Path = "$binDir;$env:Path"
        Write-Warn "PATH updated. You may need to restart your terminal."
    }

    # Run onboarding
    Write-Info "Running onboarding..."
    & $venvPython -m kabot onboard

    Write-Host ""
    Write-Info "Installation complete!"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Login to a provider: kabot auth login [openai|anthropic|google|kimi|minimax]"
    Write-Host "  2. See all methods: kabot auth methods <provider>"
    Write-Host "  3. Check auth status: kabot auth status"
    Write-Host "  4. Start the gateway: kabot gateway"
    Write-Host "  5. Or chat directly: kabot agent -m 'Hello!'"
    Write-Host ""
    Write-Host "Documentation: https://github.com/YOUR_ORG/kabot"
    Write-Host ""
    Write-Host "Note: If 'kabot' command is not found, restart your terminal or run:"
    Write-Host "  `$env:Path = `"$binDir;`$env:Path`""
}

Main
