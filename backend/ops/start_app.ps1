param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$InstallDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$requirements = Join-Path $projectRoot "requirements.txt"
$envFile = Join-Path $projectRoot ".env.local"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv (Join-Path $projectRoot ".venv")
}

if ($InstallDeps -or -not (Test-Path (Join-Path $projectRoot ".venv\.deps_installed"))) {
    Write-Host "Installing dependencies..."
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r $requirements
    New-Item -Path (Join-Path $projectRoot ".venv\.deps_installed") -ItemType File -Force | Out-Null
}

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        if ($line -notmatch "=") { return }
        $pair = $line.Split("=", 2)
        $name = $pair[0].Trim()
        $value = $pair[1].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

if (-not $env:FLASK_SECRET_KEY) {
    $bytes = New-Object "System.Byte[]" 48
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $secret = [Convert]::ToBase64String($bytes)
    [Environment]::SetEnvironmentVariable("FLASK_SECRET_KEY", $secret, "Process")
    Add-Content -Path $envFile -Value "FLASK_SECRET_KEY=$secret"
}

if (-not $env:SESSION_COOKIE_SECURE) {
    [Environment]::SetEnvironmentVariable("SESSION_COOKIE_SECURE", "1", "Process")
}
if (-not $env:TRUST_PROXY_HEADERS) {
    [Environment]::SetEnvironmentVariable("TRUST_PROXY_HEADERS", "1", "Process")
}

Set-Location $projectRoot
Write-Host "Starting waitress on http://$BindHost`:$Port"
& $venvPython -m waitress --host $BindHost --port $Port app:app
