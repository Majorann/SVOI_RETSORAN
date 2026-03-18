param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 5000,
    [switch]$InstallDeps,
    [switch]$InstallOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$arguments = @("run_local.py", "--host", $BindHost, "--port", $Port)
if ($InstallDeps) {
    $arguments += "--install-deps"
}
if ($InstallOnly) {
    $arguments += "--install-only"
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @arguments
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @arguments
} else {
    throw "Python 3 is not available in PATH."
}
