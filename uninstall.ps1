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