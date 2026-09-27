<#
.SYNOPSIS
    Uninstalls Binance Futures Paper Trading Bot from Windows Startup folder.
#>

$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "Binance-Futures-Paper-Bot.lnk"

if (Test-Path $shortcutPath) {
    Remove-Item -Path $shortcutPath -Force
    Write-Host "Autostart shortcut removed from Startup folder." -ForegroundColor Green
} else {
    Write-Host "Autostart shortcut was not found in Startup folder." -ForegroundColor Yellow
}
