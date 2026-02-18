<#
.SYNOPSIS
    Uninstalls Kabot from Windows systems by removing services, PATH entries, and installation files.

.DESCRIPTION
    This script performs a complete uninstallation of Kabot from Windows systems. It handles:
    - Stopping and removing the Kabot Windows service
    - Removing Kabot paths from the user's PATH environment variable
    - Deleting the installation directory and all associated files
    - Providing rollback capabilities if operations fail
    - Validating administrator privileges for service operations

.PARAMETER KeepConfig
    Preserves the Kabot configuration directory during uninstallation.

.PARAMETER DryRun
    Shows what actions would be performed without actually executing them.

.PARAMETER ServiceName
    Specifies the name of the Kabot service to remove. Defaults to "KabotService".

.PARAMETER InstallPath
    Specifies the Kabot installation directory. Defaults to "$env:USERPROFILE\.kabot".

.PARAMETER Force
    Bypasses confirmation prompts for destructive operations.

.EXAMPLE
    .\uninstall.ps1
    Performs a standard uninstallation with confirmation prompts.

.EXAMPLE
    .\uninstall.ps1 -KeepConfig -DryRun
    Shows what would be uninstalled while preserving configuration files.

.EXAMPLE
    .\uninstall.ps1 -Force -ServiceName "CustomKabotService"
    Forces uninstallation of a custom-named service without prompts.

.NOTES
    - Requires administrator privileges for service operations
    - Creates a rollback log for failed operations
    - Handles multiple PATH entry formats and edge cases
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(HelpMessage = "Preserve configuration files during uninstallation")]
    [switch]$KeepConfig,

    [Parameter(HelpMessage = "Show what actions would be performed without executing them")]
    [switch]$DryRun,

    [Parameter(HelpMessage = "Name of the Kabot service to remove")]
    [ValidateNotNullOrEmpty()]
    [string]$ServiceName = "KabotService",

    [Parameter(HelpMessage = "Path to the Kabot installation directory")]
    [ValidateNotNullOrEmpty()]
    [string]$InstallPath = "$env:USERPROFILE\.kabot",

    [Parameter(HelpMessage = "Bypass confirmation prompts for destructive operations")]
    [switch]$Force
)

# Initialize error tracking and rollback capabilities
$script:RollbackActions = @()
$script:UninstallErrors = @()
$script:OperationLog = @()

function Write-OperationLog {
    param([string]$Message, [string]$Level = "Info")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    $script:OperationLog += $logEntry

    switch ($Level) {
        "Error" { Write-Error $Message }
        "Warning" { Write-Warning $Message }
        "Info" { Write-Output $Message }
        "Verbose" { Write-Verbose $Message }
    }
}

function Test-AdministratorPrivileges {
    <#
    .SYNOPSIS
        Checks if the current PowerShell session has administrator privileges.
    #>
    try {
        $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        Write-OperationLog "Failed to check administrator privileges: $($_.Exception.Message)" "Warning"
        return $false
    }
}

function Remove-KabotFromPath {
    <#
    .SYNOPSIS
        Removes all Kabot-related paths from the user's PATH environment variable.
    .DESCRIPTION
        Handles multiple edge cases including:
        - Path at the beginning of PATH (no leading semicolon)
        - Path at the end of PATH (no trailing semicolon)
        - Path in the middle of PATH (surrounded by semicolons)
        - Multiple occurrences of the same path
        - Different path formats (forward/backward slashes)
    #>
    param([string]$PathToRemove)

    try {
        $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
        if (-not $userPath) {
            Write-OperationLog "User PATH environment variable is empty or not found" "Warning"
            return $true
        }

        # Normalize the path to remove for comparison
        $normalizedPathToRemove = $PathToRemove.Replace('/', '\').TrimEnd('\')

        # Check if the path exists in PATH
        $pathExists = $false
        $pathEntries = $userPath -split ';'
        foreach ($entry in $pathEntries) {
            $normalizedEntry = $entry.Replace('/', '\').TrimEnd('\')
            if ($normalizedEntry -eq $normalizedPathToRemove) {
                $pathExists = $true
                break
            }
        }

        if (-not $pathExists) {
            Write-OperationLog "Path not found in user PATH: $PathToRemove" "Info"
            return $true
        }

        if ($DryRun) {
            Write-OperationLog "Would remove from PATH: $PathToRemove" "Info"
            return $true
        }

        # Create backup for rollback
        $script:RollbackActions += @{
            Action = "RestorePath"
            OriginalPath = $userPath
        }

        # Remove all occurrences of the path (handle various formats)
        $escapedPath = [regex]::Escape($normalizedPathToRemove)

        # Pattern to match the path in various positions:
        # - At the beginning: "path;" or "path" (if it's the only entry)
        # - In the middle: ";path;"
        # - At the end: ";path"
        $patterns = @(
            "^$escapedPath;",           # Beginning with trailing semicolon
            ";$escapedPath;",           # Middle with surrounding semicolons
            ";$escapedPath$",           # End with leading semicolon
            "^$escapedPath$"            # Only entry
        )

        $newPath = $userPath
        foreach ($pattern in $patterns) {
            $newPath = $newPath -replace $pattern, ""
        }

        # Clean up any double semicolons that might result
        $newPath = $newPath -replace ";;+", ";"
        $newPath = $newPath.Trim(';')

        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-OperationLog "Successfully removed from PATH: $PathToRemove" "Info"
        return $true
    }
    catch {
        $errorMsg = "Failed to remove path from PATH environment variable: $($_.Exception.Message)"
        Write-OperationLog $errorMsg "Error"
        $script:UninstallErrors += $errorMsg
        return $false
    }
}

function Stop-KabotService {
    <#
    .SYNOPSIS
        Safely stops the Kabot Windows service with proper error handling.
    #>
    param([string]$Name)

    try {
        $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if (-not $service) {
            Write-OperationLog "Service '$Name' not found" "Info"
            return $true
        }

        if ($service.Status -eq 'Stopped') {
            Write-OperationLog "Service '$Name' is already stopped" "Info"
            return $true
        }

        if ($DryRun) {
            Write-OperationLog "Would stop service: $Name" "Info"
            return $true
        }

        Write-OperationLog "Stopping service: $Name" "Info"
        Stop-Service -Name $Name -Force -ErrorAction Stop

        # Wait for service to stop with timeout
        $timeout = 30
        $timer = 0
        while ((Get-Service -Name $Name).Status -ne 'Stopped' -and $timer -lt $timeout) {
            Start-Sleep -Seconds 1
            $timer++
        }

        if ((Get-Service -Name $Name).Status -ne 'Stopped') {
            throw "Service did not stop within $timeout seconds"
        }

        Write-OperationLog "Successfully stopped service: $Name" "Info"
        return $true
    }
    catch {
        $errorMsg = "Failed to stop service '$Name': $($_.Exception.Message)"
        Write-OperationLog $errorMsg "Error"
        $script:UninstallErrors += $errorMsg
        return $false
    }
}

function Remove-KabotService {
    <#
    .SYNOPSIS
        Removes the Kabot Windows service with proper error handling and rollback support.
    #>
    param([string]$Name)

    try {
        $service = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if (-not $service) {
            Write-OperationLog "Service '$Name' not found" "Info"
            return $true
        }

        if ($DryRun) {
            Write-OperationLog "Would remove service: $Name" "Info"
            return $true
        }

        # Store service information for potential rollback
        $script:RollbackActions += @{
            Action = "ServiceRemoved"
            ServiceName = $Name
            ServiceInfo = $service
        }

        Write-OperationLog "Removing service: $Name" "Info"

        # Use sc.exe for more reliable service removal
        $result = & sc.exe delete $Name 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "sc.exe delete failed with exit code $LASTEXITCODE`: $result"
        }

        Write-OperationLog "Successfully removed service: $Name" "Info"
        return $true
    }
    catch {
        $errorMsg = "Failed to remove service '$Name': $($_.Exception.Message)"
        Write-OperationLog $errorMsg "Error"
        $script:UninstallErrors += $errorMsg
        return $false
    }
}

function Remove-InstallationDirectory {
    <#
    .SYNOPSIS
        Removes the Kabot installation directory with proper error handling.
    #>
    param([string]$Path, [bool]$KeepConfig)

    try {
        if (-not (Test-Path $Path)) {
            Write-OperationLog "Installation directory not found: $Path" "Info"
            return $true
        }

        if ($KeepConfig) {
            Write-OperationLog "Keeping configuration directory as requested: $Path" "Info"
            return $true
        }

        if ($DryRun) {
            Write-OperationLog "Would remove directory: $Path" "Info"
            return $true
        }

        # Create backup information for rollback
        $script:RollbackActions += @{
            Action = "DirectoryRemoved"
            Path = $Path
        }

        Write-OperationLog "Removing installation directory: $Path" "Info"
        Remove-Item -Path $Path -Recurse -Force -ErrorAction Stop
        Write-OperationLog "Successfully removed installation directory: $Path" "Info"
        return $true
    }
    catch {
        $errorMsg = "Failed to remove installation directory '$Path': $($_.Exception.Message)"
        Write-OperationLog $errorMsg "Error"
        $script:UninstallErrors += $errorMsg
        return $false
    }
}

function Invoke-Rollback {
    <#
    .SYNOPSIS
        Attempts to rollback completed operations when uninstallation fails.
    #>
    if ($script:RollbackActions.Count -eq 0) {
        Write-OperationLog "No rollback actions to perform" "Info"
        return
    }

    Write-OperationLog "Attempting to rollback completed operations..." "Warning"

    # Reverse the order of rollback actions
    for ($i = $script:RollbackActions.Count - 1; $i -ge 0; $i--) {
        $action = $script:RollbackActions[$i]

        try {
            switch ($action.Action) {
                "RestorePath" {
                    [Environment]::SetEnvironmentVariable("PATH", $action.OriginalPath, "User")
                    Write-OperationLog "Restored original PATH environment variable" "Info"
                }
                "ServiceRemoved" {
                    Write-OperationLog "Cannot automatically restore removed service: $($action.ServiceName)" "Warning"
                    Write-OperationLog "Manual service restoration may be required" "Warning"
                }
                "DirectoryRemoved" {
                    Write-OperationLog "Cannot restore removed directory: $($action.Path)" "Warning"
                    Write-OperationLog "Directory contents have been permanently deleted" "Warning"
                }
            }
        }
        catch {
            Write-OperationLog "Failed to rollback action '$($action.Action)': $($_.Exception.Message)" "Error"
        }
    }
}

function Confirm-UninstallOperation {
    <#
    .SYNOPSIS
        Prompts user for confirmation of destructive operations.
    #>
    param([string]$Operation)

    if ($Force -or $DryRun) {
        return $true
    }

    $response = Read-Host "Are you sure you want to $Operation? (y/N)"
    return ($response -match '^[Yy]([Ee][Ss])?$')
}

# Main uninstallation logic
try {
    Write-OperationLog "Starting Kabot uninstallation process" "Info"

    if ($DryRun) {
        Write-OperationLog "DRY RUN MODE - No actual changes will be made" "Info"
    }

    # Validate parameters
    if (-not (Test-Path $InstallPath -IsValid)) {
        throw "Invalid installation path specified: $InstallPath"
    }

    # Check for administrator privileges if service operations are needed
    $serviceExists = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($serviceExists -and -not (Test-AdministratorPrivileges)) {
        throw "Administrator privileges are required to remove the Windows service '$ServiceName'. Please run PowerShell as Administrator."
    }

    # Confirm destructive operations
    if (-not $DryRun) {
        $confirmMessage = "uninstall Kabot (Service: $ServiceName, Path: $InstallPath)"
        if (-not (Confirm-UninstallOperation $confirmMessage)) {
            Write-OperationLog "Uninstallation cancelled by user" "Info"
            exit 0
        }
    }

    $allOperationsSuccessful = $true

    # Step 1: Stop the service
    if ($serviceExists) {
        Write-OperationLog "Step 1: Stopping Kabot service" "Info"
        if (-not (Stop-KabotService -Name $ServiceName)) {
            $allOperationsSuccessful = $false
        }
    } else {
        Write-OperationLog "Step 1: No Kabot service found to stop" "Info"
    }

    # Step 2: Remove the service
    if ($serviceExists -and $allOperationsSuccessful) {
        Write-OperationLog "Step 2: Removing Kabot service" "Info"
        if (-not (Remove-KabotService -Name $ServiceName)) {
            $allOperationsSuccessful = $false
        }
    } else {
        Write-OperationLog "Step 2: No Kabot service found to remove" "Info"
    }

    # Step 3: Remove from PATH
    Write-OperationLog "Step 3: Removing Kabot from PATH environment variable" "Info"
    $kabotPath = Join-Path $InstallPath "venv\Scripts"
    if (-not (Remove-KabotFromPath -PathToRemove $kabotPath)) {
        $allOperationsSuccessful = $false
    }

    # Step 4: Remove installation directory
    Write-OperationLog "Step 4: Removing installation directory" "Info"
    if (-not (Remove-InstallationDirectory -Path $InstallPath -KeepConfig $KeepConfig)) {
        $allOperationsSuccessful = $false
    }

    # Final status
    if ($allOperationsSuccessful) {
        if (-not $DryRun) {
            Write-OperationLog "Kabot uninstalled successfully" "Info"
        } else {
            Write-OperationLog "Dry run completed - all operations would succeed" "Info"
        }
    } else {
        Write-OperationLog "Uninstallation completed with errors" "Warning"
        Write-OperationLog "Errors encountered:" "Error"
        foreach ($error in $script:UninstallErrors) {
            Write-OperationLog "  - $error" "Error"
        }

        if (-not $DryRun) {
            Invoke-Rollback
        }
        exit 1
    }
}
catch {
    $criticalError = "Critical error during uninstallation: $($_.Exception.Message)"
    Write-OperationLog $criticalError "Error"

    if (-not $DryRun) {
        Write-OperationLog "Attempting rollback due to critical error..." "Warning"
        Invoke-Rollback
    }

    exit 1
}
finally {
    # Save operation log for troubleshooting
    if ($script:OperationLog.Count -gt 0) {
        $logPath = Join-Path $env:TEMP "kabot_uninstall_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
        try {
            $script:OperationLog | Out-File -FilePath $logPath -Encoding UTF8
            Write-OperationLog "Operation log saved to: $logPath" "Info"
        }
        catch {
            Write-OperationLog "Failed to save operation log: $($_.Exception.Message)" "Warning"
        }
    }
}