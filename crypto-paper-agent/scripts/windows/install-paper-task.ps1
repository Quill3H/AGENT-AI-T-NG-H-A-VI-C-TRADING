param([string]$JournalDir = '', [string]$PythonPath = '', [string]$TaskName = 'CryptoPaperResearchBackend')

$ErrorActionPreference = 'Stop'
$launcher = (Resolve-Path (Join-Path $PSScriptRoot 'run-paper-server.ps1')).Path
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task $TaskName already exists. Inspect/uninstall it explicitly before changing its account."
}
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$escapedLauncher = '"' + $launcher + '"'
$arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $escapedLauncher -Port 8765"
if ($JournalDir) {
    $resolvedJournal = [System.IO.Path]::GetFullPath($JournalDir)
    if ($resolvedJournal.Contains('"')) { throw 'Invalid journal path' }
    $arguments += ' -JournalDir "' + $resolvedJournal + '"'
}
if ($PythonPath) {
    $resolvedPython = [System.IO.Path]::GetFullPath($PythonPath)
    if ($resolvedPython.Contains('"')) { throw 'Invalid Python path' }
    $arguments += ' -PythonPath "' + $resolvedPython + '"'
}
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Write-Output "Installed $TaskName for $user (logon, hidden, 3 crash retries). Account is preserved. Start: Start-ScheduledTask -TaskName $TaskName"
