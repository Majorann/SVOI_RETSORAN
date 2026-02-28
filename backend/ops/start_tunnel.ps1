param(
    [Parameter(Mandatory = $true)]
    [string]$Hostname,
    [string]$TunnelName = "svoi-restoran",
    [string]$LocalService = "http://127.0.0.1:8000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Find-Cloudflared {
    $candidates = @(
        "cloudflared",
        "C:\Program Files (x86)\cloudflared\cloudflared.exe",
        "C:\Program Files\cloudflared\cloudflared.exe"
    )
    foreach ($candidate in $candidates) {
        try {
            $resolved = (Get-Command $candidate -ErrorAction Stop).Source
            if ($resolved) { return $resolved }
        } catch {
            if (Test-Path $candidate) { return $candidate }
        }
    }
    throw "cloudflared not found. Install it first."
}

$cloudflared = Find-Cloudflared
$cfDir = Join-Path $HOME ".cloudflared"
$certPath = Join-Path $cfDir "cert.pem"

if ($Hostname -match "_") {
    throw "Hostname '$Hostname' contains '_' and is invalid for public web hostnames."
}

if (-not (Test-Path $certPath)) {
    Write-Host "No Cloudflare cert found. Opening browser for login..."
    & $cloudflared tunnel login
    if (-not (Test-Path $certPath)) {
        throw "Cloudflare login was not completed. Run this script again after login."
    }
}

$tunnelsRaw = & $cloudflared tunnel list --output json
$tunnels = $tunnelsRaw | ConvertFrom-Json
$existing = $tunnels | Where-Object { $_.name -eq $TunnelName } | Select-Object -First 1

if (-not $existing) {
    Write-Host "Creating tunnel '$TunnelName'..."
    & $cloudflared tunnel create $TunnelName | Out-Host
    $tunnels = (& $cloudflared tunnel list --output json) | ConvertFrom-Json
    $existing = $tunnels | Where-Object { $_.name -eq $TunnelName } | Select-Object -First 1
}

if (-not $existing) {
    throw "Tunnel '$TunnelName' was not created."
}

$tunnelId = $existing.id
$credentialsFile = Join-Path $cfDir "$tunnelId.json"
if (-not (Test-Path $credentialsFile)) {
    throw "Credentials file not found: $credentialsFile"
}

Write-Host "Binding DNS route: $Hostname -> $TunnelName"
& $cloudflared tunnel route dns $TunnelName $Hostname | Out-Host

$configPath = Join-Path $cfDir "config.yml"
$credentialsYaml = $credentialsFile.Replace("\", "/")
$config = @(
    "tunnel: $tunnelId",
    "credentials-file: $credentialsYaml",
    "",
    "ingress:",
    "  - hostname: $Hostname",
    "    service: $LocalService",
    "  - service: http_status:404"
) -join "`n"

$config | Set-Content -Path $configPath -Encoding UTF8

Write-Host "Starting tunnel '$TunnelName' for $Hostname ..."
& $cloudflared tunnel run $TunnelName
