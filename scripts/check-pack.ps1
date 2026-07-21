[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9]+(?:-[a-z0-9]+)*$')]
    [string]$PackId
)

$ErrorActionPreference = "Stop"
$repository = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repository ".venv/Scripts/python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing .venv Python interpreter; run scripts/bootstrap.ps1 first."
}

& $python -m skillpack_tools --root $repository check-pack $PackId
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    exit $exitCode
}
