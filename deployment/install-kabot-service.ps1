# Kabot Windows Service Installer
param([switch], [switch], [switch])

 = ":USERPROFILE\.kabot\venv\Scripts\python.exe"
 = "KabotGateway"

function Install-KabotService {
    Write-Host "Installing Kabot service..." -ForegroundColor Cyan
    if (-not (Test-Path )) {
        Write-Host "Error: Kabot not found. Run: kabot onboard" -ForegroundColor Red
        exit 1
    }
    
     = New-ScheduledTaskAction -Execute  -Argument "-m kabot gateway"
     = New-ScheduledTaskTrigger -AtLogOn -User :USERNAME
     = New-ScheduledTaskPrincipal -UserId :USERNAME -LogonType Interactive
     = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    
    Register-ScheduledTask -TaskName  -Action  -Trigger  -Principal  -Settings  -Description "Kabot AI Gateway" -Force | Out-Null
    Write-Host "OK Installed. Start with: Start-ScheduledTask -TaskName " -ForegroundColor Green
}

function Uninstall-KabotService {
    Unregister-ScheduledTask -TaskName  -Confirm: -ErrorAction Stop
    Write-Host "OK Uninstalled" -ForegroundColor Green
}

function Install-StartupShortcut {
     = [Environment]::GetFolderPath('Startup')
     = Join-Path  "kabot-startup.bat"
     = Join-Path  "Kabot.lnk"
    
     = New-Object -ComObject WScript.Shell
     = .CreateShortcut()
    .TargetPath = 
    .WindowStyle = 7
    .Save()
    Write-Host "OK Startup shortcut created" -ForegroundColor Green
}

if () { Install-KabotService }
elseif () { Uninstall-KabotService }
elseif () { Install-StartupShortcut }
else {
    Write-Host "Kabot Service Installer" -ForegroundColor Cyan
    Write-Host "Usage:"
    Write-Host "  -Install        Install as scheduled task"
    Write-Host "  -StartupFolder  Add to Startup folder"
    Write-Host "  -Uninstall      Remove service"
}
