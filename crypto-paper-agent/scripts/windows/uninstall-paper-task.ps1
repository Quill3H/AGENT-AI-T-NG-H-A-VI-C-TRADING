$taskName = 'CryptoPaperResearchBackend'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Output "Removed $taskName. Journal and logs remain on disk."
} else {
    Write-Output "$taskName is not installed."
}
