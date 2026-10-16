param([string]$TaskName = 'CryptoPaperResearchBackend', [int]$Port = 8765)
& (Join-Path $PSScriptRoot 'manage-paper-task.ps1') -Action Uninstall -TaskName $TaskName -Port $Port
