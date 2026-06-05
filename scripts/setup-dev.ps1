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

$Node = Get-Command node -ErrorAction SilentlyContinue
$Npm = Get-Command npm -ErrorAction SilentlyContinue
if ($Node -and $Npm) {
    Write-Host "Node: $(& $Node.Source --version)"
    Write-Host "npm: $(& $Npm.Source --version)"
} else {
    Write-Warning "Node.js LTS is not on PATH. Install Node.js LTS, reopen PowerShell, then verify with: node --version; npm --version"
}

Write-Host "Dev environment ready."
Write-Host "Run tests with: .\scripts\test.ps1"
