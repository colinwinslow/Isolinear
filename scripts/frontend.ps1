[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "build", "test", "serve")]
    [string]$Action = "test",
    [Parameter(ValueFromRemainingArguments = $true, Position = 1)]
    [string[]]$ExtraArgs,
    [Parameter()]
    [int]$Port = 8765
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $RepoRoot "frontend"
$PackageJson = Join-Path $FrontendRoot "package.json"
$ResolveNodeScript = Join-Path $PSScriptRoot "lib\resolve-node.ps1"
. $ResolveNodeScript

if (-not (Test-Path -LiteralPath $PackageJson)) {
    throw "Frontend package not found: $PackageJson"
}

$Node = Resolve-NodeTool -ToolName node
$Npm = Resolve-NodeTool -ToolName npm
$NodeDir = Split-Path -Parent $Node
if (($env:PATH -split ";") -notcontains $NodeDir) {
    $env:PATH = "$NodeDir;$env:PATH"
}

Write-Host "Node: $(& $Node --version)"
Write-Host "npm: $(& $Npm --version)"

if ($Action -eq "install") {
    & $Npm --prefix $FrontendRoot install @ExtraArgs
    exit $LASTEXITCODE
}

if ($Action -eq "build") {
    & $Npm --prefix $FrontendRoot run build -- @ExtraArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    $PackagedDist = Join-Path $RepoRoot "custom_components\isolinear\frontend\dist"
    New-Item -ItemType Directory -Force -Path $PackagedDist | Out-Null
    Copy-Item -Force -LiteralPath (Join-Path $FrontendRoot "dist\isolinear-card.js") -Destination (Join-Path $PackagedDist "isolinear-card.js")
    exit $LASTEXITCODE
}

if ($Action -eq "test") {
    & $Npm --prefix $FrontendRoot test -- @ExtraArgs
    exit $LASTEXITCODE
}

if ($Action -eq "serve") {
    $Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        $Python = "C:\Users\c.winslow\AppData\Local\Python\bin\python.exe"
    }
    & $Python -m http.server $Port --bind 127.0.0.1 --directory $FrontendRoot
    exit $LASTEXITCODE
}
