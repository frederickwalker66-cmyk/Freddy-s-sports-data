# Freddy's Picks AI - laptop development + phone/cloud model control.
# Commands execute existing research-only code; no auto-bets or model promotion.
[CmdletBinding()]
param(
    [ValidateSet("status","setup","sync","test","run_nba","run_nfl","run_nhl","run_all","phone","run_phone","repo","edit")]
    [string]$Action = "status",
    [ValidateRange(1,35)]
    [int]$Days = 7
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repoUrl = "https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data"
Push-Location $repoRoot
try {
    switch ($Action) {
        "setup" {
            & (Join-Path $PSScriptRoot "windows_setup.ps1")
            if (-not $?) { throw "Setup failed." }
            break
        }
        "phone" {
            Start-Process "$repoUrl/actions/workflows/freddys-command-center.yml"
            Write-Host "GitHub sign-in and Run workflow are required on your phone."
            break
        }
        "run_phone" {
            Start-Process "$repoUrl/actions/workflows/v8-one-command.yml"
            Write-Host "Select the exact sport or run_all in GitHub Actions."
            break
        }
        "repo" {
            Start-Process $repoUrl
            break
        }
        "edit" {
            if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
                throw "VS Code command 'code' is not on PATH. Open the repo folder manually in VS Code."
            }
            & code $repoRoot
            if ($LASTEXITCODE -ne 0) { throw "VS Code launch failed." }
            break
        }
        "sync" {
            if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git not installed." }
            if (-not (Test-Path ".git")) { throw "Repository must be cloned with Git." }
            $active = (& git branch --show-current).Trim()
            if ($LASTEXITCODE -ne 0 -or $active -ne "main") {
                throw "Switch to main manually after saving your engineering work; sync only updates main."
            }
            $changes = @(& git status --porcelain)
            if ($LASTEXITCODE -ne 0 -or ($changes | Where-Object { $_ }).Count -gt 0) {
                throw "Local changes exist. Commit or stash them yourself first; sync will not discard your work."
            }
            & git pull --ff-only origin main
            if ($LASTEXITCODE -ne 0) { throw "Fast-forward pull failed. Your local files were not reset." }
            Write-Host "Laptop main branch updated from GitHub."
            break
        }
        "status" {
            if (-not (Get-Command git -ErrorAction SilentlyContinue) -or -not (Test-Path ".git")) {
                throw "Git clone not found. Install Git and clone the repository."
            }
            & git status --short --branch
            if ($LASTEXITCODE -ne 0) { throw "Git status failed." }
            Write-Host ""
            Write-Host "Laptop = local code engineering. Phone = signed-in GitHub cloud commands."
            Write-Host "Cloud control: $repoUrl/actions/workflows/freddys-command-center.yml"
            Write-Host "Per-sport run: $repoUrl/actions/workflows/v8-one-command.yml"
            Write-Host "Champion-001 remains frozen. Passing tests do not certify betting EV."
            break
        }
        default {
            $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
            if (-not (Test-Path $venvPython)) {
                throw "Run .\scripts\windows_setup.ps1 first to create your local .venv."
            }
            if ($Action -eq "test") {
                & $venvPython -m unittest discover -s tests -v
                if ($LASTEXITCODE -ne 0) { throw "Regression tests failed; no deployment attempted." }
                break
            }
            $command = @{
                "run_nba"="run_nba"
                "run_nfl"="run_nfl"
                "run_nhl"="run_nhl"
                "run_all"="run_all"
            }[$Action]
            if (-not $command) { throw "Unsupported local research action." }
            $output = Join-Path $repoRoot ("local_work\research\" + $command)
            Write-Host "Running local $command research. Unverified data remain HOLD."
            & $venvPython v8_one_command.py --command $command --days $Days --output-dir $output
            if ($LASTEXITCODE -ne 0) { throw "$command failed. Check errors; no bet was placed." }
            $summary = Join-Path $output "FULL_STACK_ALL_IN_ONE_REPORT.md"
            if (Test-Path $summary) {
                Write-Host "Research results: $summary"
            } else {
                Write-Host "Research output: $output"
            }
            Write-Host "These are research outputs, not independently certified betting picks."
            break
        }
    }
}
finally {
    Pop-Location
}
