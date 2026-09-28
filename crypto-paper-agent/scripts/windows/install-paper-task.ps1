param([string]$JournalDir = '', [string]$PythonPath = '')

$ErrorActionPreference = 'Stop'
$launcher = (Resolve-Path (Join-Path $PSScriptRoot 'run-paper-server.ps1')).Path
$taskName = 'CryptoPaperResearchBackend'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$escapedLauncher = '"' + $launcher + '"'
$arguments = "-NoProfile -ExecutionPolicy Bypass -File $escapedLauncher -Port 8765"
if ($JournalDir) {
    $resolvedJournal = [System.IO.Path]::GetFullPath($JournalDir)
    $arguments += ' -JournalDir "' + $resolvedJournal + '"'
}
if ($PythonPath) {
    $resolvedPython = [System.IO.Path]::GetFullPath($PythonPath)
    $arguments += ' -PythonPath "' + $resolvedPython + '"'
}
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Output "Installed $taskName for $user. Start manually: Start-ScheduledTask -TaskName $taskName"
