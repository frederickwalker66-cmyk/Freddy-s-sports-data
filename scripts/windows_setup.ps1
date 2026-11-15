# Freddy's Picks AI - Windows engineering workstation setup.
# Runs locally on the owner's laptop. Does not fetch/modify Champion-001.
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipDependencies
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
        throw "A Git clone is required. Clone the repository before running setup (not a downloaded ZIP)."
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git is missing. Install Git for Windows and reopen PowerShell."
    }

    # Prefer the same Python minor version that GitHub Actions validates.
    $pythonCmd = $null
    $pythonPrefix = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12)"
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = "py"
            $pythonPrefix = @("-3.12")
        }
    }
    if (-not $pythonCmd) {
        foreach ($candidate in @("python", "python3")) {
            if (Get-Command $candidate -ErrorAction SilentlyContinue) {
                & $candidate -c "import sys; assert sys.version_info[:2] == (3, 12)"
                if ($LASTEXITCODE -eq 0) {
                    $pythonCmd = $candidate
                    break
                }
            }
        }
    }
    if (-not $pythonCmd) {
        throw "Python 3.12 is required to match GitHub CI. Install Python 3.12 and reopen PowerShell."
    }

    $venv = Join-Path $repoRoot ".venv"
    if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
        Write-Host "Creating local virtual environment (.venv) ..."
        & $pythonCmd @pythonPrefix -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
    }
    $venvPython = Join-Path $venv "Scripts\python.exe"
    if (-not $SkipDependencies) {
        Write-Host "Installing declared engineering/test dependencies ..."
        & $venvPython -m pip install -r requirements-calibration.txt -r requirements-injury-pdf.txt
        if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed; check internet and pip output." }
    }
    if (-not $SkipTests) {
        Write-Host "Running complete offline safety/test suite ..."
        & $venvPython -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw "Local regression tests failed. No model was deployed." }
    }
    Write-Host ""
    Write-Host "Ready: Freddy's Picks AI V8 laptop engineering environment."
    Write-Host "Next: .\scripts\windows_model.ps1 -Action status"
    Write-Host "Phone control: https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/freddys-command-center.yml"
    Write-Host "Champion-001 has NOT been edited; no wager or model certification was created."
}
finally {
    Pop-Location
}
