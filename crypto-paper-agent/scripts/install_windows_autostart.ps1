<#
.SYNOPSIS
    Installs Binance Futures Paper Trading Bot to automatically start on Windows user login.
.DESCRIPTION
    Creates a minimized shortcut in the Windows user's Startup folder pointing to start-paper-web.cmd.
    Avoids duplicate instances and includes process watchdog recovery.
#>

$repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$launcher = Join-Path $repoRoot "start-paper-web.cmd"

if (-not (Test-Path $launcher)) {
    Write-Error "Launcher script not found at: $launcher"
    exit 1
}

$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "Binance-Futures-Paper-Bot.lnk"

$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "cmd.exe"
$shortcut.Arguments = "/c `"$launcher`" 8765"
$shortcut.WorkingDirectory = $repoRoot
$shortcut.WindowStyle = 7  # Minimized window
$shortcut.Description = "Binance Futures Paper Trading Bot - Loopback Local Web"
$shortcut.Save()

Write-Host "============================================================" -ForegroundColor Green
Write-Host "Windows Autostart Installed Successfully!" -ForegroundColor Green
Write-Host "Shortcut created at:" -ForegroundColor Cyan
Write-Host "  $shortcutPath"
Write-Host "Target:" -ForegroundColor Cyan
Write-Host "  cmd.exe /c `"$launcher`" 8765"
Write-Host "When you log into Windows, the paper bot server will start automatically." -ForegroundColor Green
Write-Host "To remove autostart, run: .\uninstall_windows_autostart.ps1" -ForegroundColor Yellow
Write-Host "============================================================"
