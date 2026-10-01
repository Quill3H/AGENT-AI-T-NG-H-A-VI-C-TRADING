param(
    [ValidateSet('Status', 'Logs', 'Pause', 'Resume', 'StartBot', 'StopBot', 'DisableAndStop', 'Uninstall')]
    [string]$Action = 'Status',
    [string]$TaskName = 'CryptoPaperResearchBackend',
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [string]$JournalDir = ''
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$account = if ($JournalDir) { [System.IO.Path]::GetFullPath($JournalDir) } else { Join-Path $project 'data\paper_accounts\windows-paper-v3' }
$base = "http://127.0.0.1:$Port"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($Action -eq 'Logs') {
    $log = Join-Path $account 'logs\paper-server.log'
    if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Tail 100 } else { Write-Output 'No startup log at the selected account.' }
    exit 0
}
if ($Action -eq 'Status') {
    if ($task) { $task | Select-Object TaskName, State; Get-ScheduledTaskInfo -TaskName $TaskName } else { Write-Output 'Scheduled Task is not installed.' }
    try { Invoke-RestMethod -Uri "$base/api/health" -TimeoutSec 3 | ConvertTo-Json -Depth 12 } catch { Write-Output "Backend unavailable: $($_.Exception.Message)" }
    exit 0
}
if ($Action -in @('Pause', 'Resume', 'StartBot', 'StopBot')) {
    $route = @{ Pause = 'pause'; Resume = 'resume'; StartBot = 'start'; StopBot = 'stop' }[$Action]
    Invoke-RestMethod -Uri "$base/api/$route" -Method Post -TimeoutSec 5 | ConvertTo-Json -Depth 12
    Write-Output '202 means queued, not finished. Check Status/api/state for operation completion. StopBot does not stop the Windows service.'
    exit 0
}

# Disable first, then stop only a verified backend at this loopback port.
if ($task) { Disable-ScheduledTask -TaskName $TaskName | Out-Null }
$listener = Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $serverProcessId = $listener[0].OwningProcess
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$serverProcessId"
    $script = Join-Path $project 'scripts\run_local_paper_web.py'
    $health = Invoke-RestMethod -Uri "$base/api/health" -TimeoutSec 3
    if ($health.mode -ne 'PAPER_RESEARCH' -or $health.server_pid -ne $serverProcessId -or
            -not $process.CommandLine.Contains($script)) {
        throw 'Port belongs to an unverified process. Task is disabled; no process was terminated.'
    }
    Stop-Process -Id $serverProcessId
}
if ($task) { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue }
if ($Action -eq 'Uninstall' -and $task) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
Write-Output "$Action applied. No account data or logs were removed; restart will verify the last committed SQLite checkpoint."
