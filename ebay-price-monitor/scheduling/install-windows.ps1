<#
Schedules pricewatch with Windows Task Scheduler.

  powershell -ExecutionPolicy Bypass -File scheduling\install-windows.ps1              every 60 minutes
  powershell -ExecutionPolicy Bypass -File scheduling\install-windows.ps1 -Every 15    every 15 minutes
  powershell -ExecutionPolicy Bypass -File scheduling\install-windows.ps1 -Uninstall   stop and remove

Runs while you are signed in. A scan missed during sleep or shutdown runs once at the next chance.
Uses pythonw.exe so no console window pops up on each scan. Output goes to pricewatch.log.
#>
param(
    [ValidateSet(5, 10, 15, 20, 30, 60)]
    [int]$Every = 60,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "pricewatch"
$Dir = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Dir ".venv\Scripts\pythonw.exe"
$Config = Join-Path $Dir "config.yaml"
$Log = Join-Path $Dir "pricewatch.log"

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "removed $TaskName"
    exit 0
}

if (-not (Test-Path $Py)) {
    Write-Host "no virtualenv at $Dir\.venv. Run first:"
    Write-Host "  py -m venv .venv"
    Write-Host "  .venv\Scripts\python -m pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path $Config)) {
    Write-Host "no config.yaml in $Dir. Run: copy config.example.yaml config.yaml"
    exit 1
}
if (-not (Select-String -Path $Config -Pattern '^\s*client_id:\s*[^\s#]' -Quiet)) {
    Write-Host "warning: scheduled tasks do not see keys set with `$env: in PowerShell."
    Write-Host "         Put client_id and client_secret under ebay: in config.yaml or every scan will fail."
}

$Action = New-ScheduledTaskAction -Execute $Py -Argument "-m pricewatch run --log `"$Log`"" -WorkingDirectory $Dir
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Every)
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "eBay price scan (pricewatch)" -Force | Out-Null

Write-Host "installed: pricewatch scans every $Every minutes, first scan in about 1 minute"
Write-Host "log:       $Log"
Write-Host "watch log: Get-Content `"$Log`" -Wait -Tail 30"
Write-Host "run now:   Start-ScheduledTask -TaskName $TaskName"
Write-Host "remove:    powershell -ExecutionPolicy Bypass -File scheduling\install-windows.ps1 -Uninstall"
