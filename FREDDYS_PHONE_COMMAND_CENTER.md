# Freddy's Picks AI — control from Windows laptop or phone

The working research repository is [Freddy-s-sports-data](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data). GitHub-hosted workflows run in GitHub Cloud whether or not the Windows laptop and phone are switched on.

## One safe command center

Open the [Freddy's Picks AI Phone Command Center](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/freddys-command-center.yml) in your phone's web browser or laptop. Sign in to the GitHub account with repo access, choose **Run workflow**, select the main branch, select a command, then press Run workflow. The GitHub mobile app may not expose every workflow-dispatch control; a mobile web browser is more reliable.

| Command | Purpose | Paid provider API requests? |
| --- | --- | --- |
| status | Inspect actual GitHub production Actions runs, branch protection and model hold status | No |
| all_free_diagnostics | Request offline code tests, public eight-sport source capture, and outcome review | No dedicated paid provider calls |
| full_refresh_recalibrate | Request 14 independent free research jobs: tests, eight-sport source capture, prospective forecasts, outcomes, Challenger calibration/training safety, V8 readiness, NBA/NFL Sharp Edge from saved odds, NFL/NHL forward capture, all three durable grade ledgers, season L5/L10, NBA injury source, and the full-stack One Command board | **No new paid-provider calls, no bets, Champion frozen** |
| public_eight_sport_scan | Request an original ESPN source capture for the eight research leagues | No |
| code_tests | Launch full Python offline regression suite | No |
| outcome_review | Request pregame observations and published-outcome reconciliation | No dedicated paid provider calls |
| calibration_research | Run the existing research calibration safety gate | No dedicated paid provider calls |
| source_backup | Archive both connected GitHub source repositories and full history | No |
| nba_live_paid | Run an additional NBA-only SharpAPI live collection | **YES — separate consent checkbox** |
| sportsdataio_paid | Run an additional SportsDataIO source research intake | **YES — separate consent checkbox** |

Paid workflows are rejected unless you explicitly tick **I authorize this run to use paid provider API credits**. Inputs cannot execute arbitrary scripts or target arbitrary workflows; no betting or model-unfreeze command is available.

## Read the results

Open **Actions → Freddy's Picks AI — Phone Command Center → latest run → phone-dashboard** and read the **Summary**. Its ZIP artifact contains PHONE_DASHBOARD.md and PHONE_DASHBOARD.json for 30 days. Dispatched workflows start separately: a successful command request is NOT evidence that the downstream job or provider connection succeeded. The **full_refresh_recalibrate** command sends 14 independent safe workflow requests; **it is not a completed eight-sport retraining or calibration release**. Parallel tasks can inspect different archive ages. The existing outcome-completion trigger may request a subsequent Challenger recalibration, but its separate actual completed run and eligible evidence must be verified. Missing or unauthenticated forecasts mean HOLD, not a manufactured success. Tap the corresponding workflow link, open its newest run, and review actual archive receipts and timestamps.

GitHub also requests two automatic **status-only** dashboards daily. The separate eight-sport original-source collector requests public source checks at minute 27 and 53 UTC each hour; GitHub scheduling can still be delayed or dropped. The phone dashboard reports actual runs, not assumed execution.

## Repeat full model refresh and recalibration

To repeat the existing safe refresh from your phone, use the Phone Command Center workflow on `main`, choose `full_refresh_recalibrate`, and tap **Run workflow**. This requests 14 separate research workflows, including the previous eight plus NFL/NHL forward captures, all three NBA/NFL/NHL outcome grading ledgers, L5/L10 historical research, the NBA injury-source archive and the full-stack One Command board. The public website normally publishes from the One Command run afterward; it is not an instantaneous view of the dispatch. This does not charge paid odds providers or place bets.

A workflow dispatch accepted by GitHub is not a complete recalibration. Check each workflow's actual run conclusion and the calibration artifact's eligible original pregame forecast/outcome counts. Missing independently qualified forecast history means `HOLD`, no calibrated production probability, and no certified expected-value picks. The original Champion-001 remains frozen.

## Laptop: run the whole free refresh now

1. Open [Freddy's Command Center in your browser](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/freddys-command-center.yml) and sign in.
2. Click **Run workflow**, select **main**, choose **full_refresh_recalibrate**, and keep **confirm_paid_api** unchecked.
3. Click **Run workflow** again to submit. Open that run's Summary and artifact for the accepted/rejected dispatch receipt. Each downstream job has its own completion status; monitor the latest recorded run of each.
4. For the full research board, open [V8 One Command](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v8-one-command.yml) and choose **run_all** (all eight sports) or **run_nba** (NBA only). Results are research-only; source and model evidence holds still apply.

This works entirely in your laptop browser; you do not need to install Python or run PowerShell. GitHub-hosted jobs do not require your laptop to stay running. The aggregate command is NOT a verified calibration or betting-readiness release; parallel sources and grading jobs may use different timestamps.

## Laptop quick update

Open Windows PowerShell inside your working repository clone and run these commands separately:

    git switch main
    git pull --ff-only origin main
    python -m unittest discover -s tests -v

A downloaded ZIP is a snapshot and does not update itself. If there is no .git folder, clone the repo using:

    git clone https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data.git

## Existing external model blockers are not automatically repaired

The original immutable Champion-001 executable/source/weights and reference forecasts have not been authenticated from the connected GitHub repositories. Independently qualified point-in-time training history, later holdout evidence, calibrated Challenger predictions, independently verified direct DraftKings checkout prices and player-day status are not established. Therefore model release remains HOLD, certified positive-EV bets remain zero, and wagers remain zero. A passing GitHub test is operational validation only.

Track independently verifiable prerequisites in [issue 41](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/issues/41).

## Protect main (administrator action)

The repo default main branch remains unprotected. As administrator, visit **Settings → Rules → Rulesets → New branch ruleset**, target main, require pull requests and the passing validation check from **Validate NBA MLB research integrity (offline)**, restrict force pushes and deletion, and activate the ruleset. Adding this document does NOT itself activate protection.
