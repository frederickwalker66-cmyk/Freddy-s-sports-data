# Freddy's Picks AI V8 — Windows engineering, phone control

**Architecture:** Your Windows laptop is the development workstation (source code, tests, experiments and commits). GitHub stores the reviewed code and runs the existing cloud research workflows you select from your phone. The website is a read-only research dashboard; its buttons open **signed-in GitHub Actions**. A phone command runs the **GitHub-hosted model research pipeline**, not a process on your personal laptop. Your laptop can be off for GitHub-hosted Actions, subject to GitHub scheduling and usage limits.

## A. Install the engineering workstation on Windows

**One-time prerequisites:** Git for Windows, Python **3.12**, and (recommended) Visual Studio Code. Windows Package Manager, when available:

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id Microsoft.VisualStudioCode -e
```

After those installers finish, **reopen PowerShell**. In a folder you choose:

```powershell
cd $HOME\Documents
git clone https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data.git
cd Freddy-s-sports-data
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_setup.ps1
code .
```

**Simplest option:** In File Explorer open your cloned `Freddy-s-sports-data` folder and **double-click `START_FREDDYS_MODEL.cmd`**. Choose **1** for setup, **2** to run tests, **3–6** for local NBA/NFL/NHL/eight-sport scans, or **7** for the phone controls. This is a local menu, not a betting app, and does not execute arbitrary remote commands.

The setup script requires a real Git clone, creates a private `.venv`, installs only the repository's two declared optional/test requirement sets and runs **all offline regression tests**. It does **not** download a Champion model, replace any probability model, place bets, ask for sportsbook credentials or push changes. If packages cannot be installed, rerun after checking Python/pip networking; **do not** treat a failed setup as success.

If you **already have the repo cloned**, do not clone it again. Open PowerShell inside your existing clone and run just the setup command. No GitHub password or personal API key should ever be pasted into code or this public repository.

## B. Engineering commands from your laptop

Run these in your cloned repository. Each command is one PowerShell process; no global execution-policy change:

```powershell
# Read-only Git status and phone control links
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action status

# All offline safety tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action test

# Research-only exact sport or eight-sport pipelines (free public inputs)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action run_nba
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action run_nfl
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action run_nhl
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action run_all

# Only updates main when it is already selected and has NO local changes
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action sync
```

Local research files are written to `local_work/research/<command>/`, excluded from Git. They are **not** automatically published to the phone or certified as winning picks. A local scan can still be incomplete because of blocked free sources, missing provider quotes and unverified player identities.

In **VS Code**, choose **Terminal → Run Task** and select `Freddy: 1 - Set up Windows engineering`, `Run all offline regression tests`, `Run NBA research locally`, etc. These tasks use the same transparent PowerShell scripts. **Tests** (Ctrl+Shift+B is a build shortcut and may select NBA research) can be run with **Terminal → Run Test Task**.

## Audit a lost ticket without exposing your private receipts

The Windows command center now has **A. Audit a PRIVATE lost ticket**. It checks previously rejected/PASS legs, duplicate player or event exposure, all-Overs concentration and 4+ leg accumulator variance. It also summarizes **user-reported** wins/losses/pushes/voids/pending legs, without falsely claiming that an external sportsbook verified them.

1. In File Explorer, locate the fictional sample `examples/private_ticket_template.example.json` and **copy** it to `local_work/private_ticket.json` in your repo. Create the `local_work` folder if necessary; it is Git-ignored.
2. Edit the copy on your laptop using the actual exact sportsbook receipt: event IDs and UTC-offset timestamps, each player/stat/line, directions, any earlier PASS/HOLD label, reported outcomes, stake and **accepted** American ticket odds. Do not enter guesses; do not include your account number. Never commit or upload the private receipt to this public GitHub repository.
3. Double-click `START_FREDDYS_MODEL.cmd`, choose **A**, and read the local `local_work/ticket_loss_audit.json` report. Run setup (menu 1) first if Python is not ready.
4. You can also use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action ticket` from the repo root.

A ticket with **any losing leg** ordinarily loses as a conventional parlay, subject to bookmaker settlement rules. An eight-leg ticket with all Overs and repeated players is high variance and can have strong dependency between legs; this structural warning is *not* a measured probability or proof of negative EV. The tool never alters the sportsbook ticket, refunds a loss, approves future bets or computes fabricated CLV. A validated model forecast for each exact market and a defensible **joint** parlay distribution are still required for any expected-value analysis. Exact accepted tickets and final settlement need independent verification.

### Prevent repeat ticket-construction mistakes

The Challenger-only `audit_slip` preflight now additionally flags `four_or_more_legs_high_variance`, `all_overs_directional_concentration`, `same_player_multi_prop_exposure`, and `previously_passed_or_held_leg_included`. These are research caution flags, not a substitute for independent active-player confirmation, native probability generation, authenticated DraftKings checkout odds, or a measured correlation matrix. The future pick-release gate **remains HOLD**. Favor **PASS** rather than assuming a strong betting edge simply because a parlay looks plausible or historical hit rates are high.

## C. Safely develop new model changes on the laptop

Do not edit the frozen Champion-001 code or treat market odds as native predictions. Build the **Challenger research** lane separately. For a proposed source or validation repair:

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/my-model-repair
# Edit source and tests in VS Code.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows_model.ps1 -Action test
git status --short
# Stage ONLY your intended source/test files; review changes before committing.
git add path/to/changed_file.py tests/test_changed_file.py
git diff --cached
git commit -m "Explain tested research repair"
git push -u origin feature/my-model-repair
```

Open a GitHub pull request to `main`, review required CI, then merge approved changes. **Phone workflows run code from `main`**, so unmerged laptop branches cannot silently replace the phone production engine. Never force-push or use `git reset --hard` to “sync.”

## D. Operate your research from your phone (Android or iPhone)

1. Open [Freddy's Picks AI Phone Command Center](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/freddys-command-center.yml) in your mobile browser and sign in to **your own** GitHub account.
2. Tap **Run workflow**, choose the `main` branch and `full_refresh_recalibrate` (14 independent research dispatches). Leave `confirm_paid_api` **unchecked**. Tap **Run workflow** to submit.
3. Open the newest workflow run's **Summary** and its `phone-dashboard` artifact. “Dispatch accepted” means jobs were requested, **not** that source collection or calibration succeeded.
4. For a specific league, open [V8 One Command](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v8-one-command.yml) → **Run workflow** → choose `run_nba`, `run_nfl`, `run_nhl` or `run_all`. Download `v8-one-command-...` artifacts after a completed run.
5. Optional: use the mobile browser's **Add to Home screen** action on the Command Center or research website for a one-tap shortcut. This does not create a privileged API token or bypass GitHub sign-in.

The website's **Run NBA**, **Run All Sports** and **Phone Command Center** links go to GitHub Actions, not an unsecured browser-side API. No GitHub personal access token is stored in public web JavaScript.

## E. What is controlled remotely vs. still blocked

| Feature | Laptop | Phone / GitHub |
| --- | --- | --- |
| Edit Python feature engineering / tests | Yes, locally in VS Code | Read review and CI status |
| Run local NBA/NFL/NHL/all-sports research | Yes, with Python 3.12 | Launch same GitHub cloud research commands |
| Run research refresh / grading | Developer scripts and code tests | Dispatch cloud workflows and inspect results |
| Train a *research-only* Challenger model on qualified data | Possible once source evidence is genuinely available | View downstream training readiness, no auto release |
| Change frozen Champion-001 | **No** (requires original artifact and independent change authorization) | **No** |
| Certified DraftKings +EV without authenticated executable odds/native p | **No — HOLD** | **No — HOLD** |
| Wake or execute arbitrary code on your private laptop | Not applicable | **Not implemented**; GitHub jobs run on GitHub-hosted machines |

**Safety:** Keep all private model files and API credentials **off the public repository**. The ignore rules cover `.env`, `.venv`, and `local_work`; review `git diff --cached` before pushing. Store provider keys using GitHub Actions **Settings → Secrets and variables → Actions** only when appropriate. Avoid a self-hosted Actions runner attached to this **public** repository without first designing network, access and job-permission isolation.

**Remaining certification blockers:** original authenticated Champion-001 executable/reference outputs, sufficient point-in-time native model predictions and independent calibration, genuine market-specific DraftKings checkout receipts, and verified player IDs/lineups/settlement. No engineering shortcut should invent these facts. Certified bets: **0**, automatic wagering: **off**, shadow stake: **$0**.

See also [Command Center operations](FREDDYS_PHONE_COMMAND_CENTER.md), [full research command guide](V8_ONE_COMMAND_PHONE_GUIDE.md) and [model evidence issue #41](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/issues/41).
