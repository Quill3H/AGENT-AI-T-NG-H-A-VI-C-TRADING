param(
    [int]$Port = 8765,
    [string]$JournalDir = '',
    [string]$PythonPath = ''
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = if ($PythonPath) { [System.IO.Path]::GetFullPath($PythonPath) } else { Join-Path $project '.venv-paper\Scripts\python.exe' }
$logs = Join-Path $project 'data\paper_sessions\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$log = Join-Path $logs 'paper-server.log'

$client = [System.Net.Sockets.TcpClient]::new()
try {
    $attempt = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
    if ($attempt.AsyncWaitHandle.WaitOne(500)) {
        try {
            $client.EndConnect($attempt)
            "$(Get-Date -Format o) Port $Port already serves a process; duplicate paper server not started." | Add-Content -LiteralPath $log
            exit 2
        } catch [System.Net.Sockets.SocketException] {
            # Connection refused: the port is available.
        }
    }
} finally {
    $client.Close()
}

if (-not (Test-Path -LiteralPath $python)) {
    "$(Get-Date -Format o) Python virtual environment missing: $python" | Add-Content -LiteralPath $log
    exit 2
}

$arguments = @((Join-Path $project 'scripts\run_local_paper_web.py'), '--port', "$Port")
if ($JournalDir) {
    $arguments += @('--journal-dir', $JournalDir)
}
"$(Get-Date -Format o) Starting PAPER/RESEARCH backend on 127.0.0.1:$Port" | Add-Content -LiteralPath $log
& $python @arguments *>> $log
exit $LASTEXITCODE
