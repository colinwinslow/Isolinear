[CmdletBinding()]
param(
    [string]$Python = $env:ISOLINEAR_PYTHON
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Requirements = Join-Path $RepoRoot "requirements-dev.txt"
$ResolveNodeScript = Join-Path $PSScriptRoot "lib\resolve-node.ps1"
. $ResolveNodeScript

$MatplotlibConfigDir = Join-Path $RepoRoot ".test-output\matplotlib"
New-Item -ItemType Directory -Force -Path $MatplotlibConfigDir | Out-Null
$env:MPLCONFIGDIR = $MatplotlibConfigDir

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($Arguments -join ' ')"
    }
}

function Resolve-Python {
    param([string]$RequestedPython)

    if ($RequestedPython) {
        if (Test-Path -LiteralPath $RequestedPython) {
            return (Resolve-Path -LiteralPath $RequestedPython).Path
        }
        throw "Requested Python was not found: $RequestedPython"
    }

    $DocumentedPython = "C:\Users\c.winslow\AppData\Local\Python\bin\python.exe"
    if (Test-Path -LiteralPath $DocumentedPython) {
        return $DocumentedPython
    }

    $PathPython = Get-Command python -ErrorAction SilentlyContinue
    if ($PathPython -and $PathPython.Source -notlike "*\WindowsApps\python.exe") {
        return $PathPython.Source
    }

    throw "Python was not found. Set ISOLINEAR_PYTHON to a Python executable or install Python and reopen PowerShell."
}

$BasePython = Resolve-Python -RequestedPython $Python
Write-Host "Using Python: $BasePython"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating virtual environment: $VenvDir"
    Invoke-Checked -FilePath $BasePython -Arguments @("-m", "venv", $VenvDir)
}

Write-Host "Upgrading pip"
Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip")

Write-Host "Installing Python dev dependencies"
Invoke-Checked -FilePath $VenvPython -Arguments @("-m", "pip", "install", "-r", $Requirements)

$FrontendPackage = Join-Path $RepoRoot "frontend\package.json"
$Node = $null
$Npm = $null
try {
    $Node = Resolve-NodeTool -ToolName node
    $Npm = Resolve-NodeTool -ToolName npm
} catch {
    Write-Warning $_.Exception.Message
}

if ($Node -and $Npm) {
    $NodeDir = Split-Path -Parent $Node
    if (($env:PATH -split ";") -notcontains $NodeDir) {
        $env:PATH = "$NodeDir;$env:PATH"
    }

    Write-Host "Node: $(& $Node --version)"
    Write-Host "npm: $(& $Npm --version)"

    if (Test-Path -LiteralPath $FrontendPackage) {
        Write-Host "Installing frontend dependencies"
        Invoke-Checked -FilePath $Npm -Arguments @("--prefix", (Join-Path $RepoRoot "frontend"), "install")
    }
}

Write-Host "Dev environment ready."
Write-Host "Run tests with: .\scripts\test.ps1"
Write-Host "Run frontend checks with: .\scripts\frontend.ps1 test"
