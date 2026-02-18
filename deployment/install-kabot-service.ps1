# Windows Service Installer for Kabot
param(
    [string]$ServiceName = "KabotService",
    [string]$DisplayName = "Kabot AI Assistant Service",
    [string]$Description = "Kabot AI Assistant Background Service"
)

# Check admin privileges - split for readability
$currentPrincipal = [Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    throw "This script requires Administrator privileges"
}

# Check if service already exists
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Warning "Service '$ServiceName' already exists. Use Remove-Service or sc.exe delete to remove it first."
    return
}

# Set paths with proper environment variables
$pythonExe = "$env:USERPROFILE\.kabot\venv\Scripts\python.exe"
$kabotScript = "$env:USERPROFILE\.kabot\venv\Scripts\kabot.exe"
$logPath = "$env:USERPROFILE\.kabot\logs\service.log"

# Validate required executables exist
if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found at: $pythonExe"
}

if (-not (Test-Path $kabotScript)) {
    throw "Kabot executable not found at: $kabotScript"
}

# Ensure logs directory exists
$logsDir = Split-Path $logPath -Parent
if (-not (Test-Path $logsDir)) {
    Write-Host "Creating logs directory: $logsDir"
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

# Prepare service configuration
$servicePath = "`"$kabotScript`" daemon --log-file `"$logPath`""

try {
    # Create the Windows service
    Write-Host "Creating service '$ServiceName'..."
    New-Service -Name $ServiceName -BinaryPathName $servicePath -DisplayName $DisplayName -Description $Description -StartupType Automatic
    Write-Host "Service '$ServiceName' created successfully"

    # Start the service
    Write-Host "Starting service '$ServiceName'..."
    Start-Service -Name $ServiceName
    Write-Host "Service '$ServiceName' started successfully"

} catch {
    # Cleanup on failure - remove service if it was created but failed to start
    Write-Error "Failed to create/start service: $_"

    # Check if service was created but failed to start
    $createdService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($createdService) {
        Write-Host "Cleaning up: Removing partially created service '$ServiceName'..."
        try {
            Remove-Service -Name $ServiceName -Force
            Write-Host "Service '$ServiceName' removed successfully"
        } catch {
            Write-Warning "Failed to remove service '$ServiceName': $_"
            Write-Warning "You may need to manually remove it using: sc.exe delete $ServiceName"
        }
    }

    throw "Service installation failed"
}