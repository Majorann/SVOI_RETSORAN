param(
    [Parameter(Mandatory = $true)]
    [string]$Hostname
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$opsDir = Resolve-Path $PSScriptRoot
$appScript = Join-Path $opsDir "start_app.ps1"
$tunnelScript = Join-Path $opsDir "start_tunnel.ps1"
$pwsh = (Get-Command powershell).Source

$appAction = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$appScript`""
$tunnelAction = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$tunnelScript`" -Hostname `"$Hostname`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "SvoiRestoran-App" -Action $appAction -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName "SvoiRestoran-Tunnel" -Action $tunnelAction -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

Write-Host "Tasks created: SvoiRestoran-App and SvoiRestoran-Tunnel"
