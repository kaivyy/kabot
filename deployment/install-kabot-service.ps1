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