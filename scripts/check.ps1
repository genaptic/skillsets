[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repository ".venv/Scripts/python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing .venv Python interpreter; run scripts/bootstrap.ps1 first."
}

& $python -m skillpack_tools --root $repository check
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}
