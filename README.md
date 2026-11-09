# Freddy's Picks AI — All-Sports Research and GitHub Control Center

**This repository contains a research-only sports evidence pipeline and automated GitHub workflows. It is not yet an independently certified real-money betting prediction engine.**

## NEW: V8 One Command — phone and laptop

**[Run NBA / Run Sports / Run Sharp / Run Edge / Model Status](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/v8-one-command.yml)** — an integrated GitHub Actions research interface, available after the V8 branch merges to main. View the [V8 phone guide](V8_ONE_COMMAND_PHONE_GUIDE.md).

- `run_nba` and `run_sports` collect bounded, historical **public research results** (up to 35 days per league) with downloadable artifacts, no paid bookmaker calls.
- `run_nba_grade` reads genuinely archived before-tipoff NBA V8 research probabilities, checks original schedule hashes and GitHub run times, and separately grades completed ESPN scores after 48h with Brier/log loss. Missing outcomes stay pending; all results remain research-only and frozen Champion-001 remains unchanged.
- `run_nba_forward` collects a fresh, original ESPN NBA schedule and completed-score history, logs strictly future before-tipoff Elo v0 research probabilities with actual UTC capture timestamps, and explicitly keeps all Champion-001 shadow certifications / EV / wagers at 0. A daily best-effort GitHub run is configured.
- `run_nba_oos` fetches a bounded genuine ESPN-published NBA score window and compares retrospective 48h-embargo Elo Brier/log-loss to an evolving home-win-rate baseline, with approximate paired day-cluster bootstrap uncertainty. No authentic time-stamped pregame forecasts, independently certified calibration or sportsbook ROI is claimed.
- `run_nba_train` collects actual pregame original-source review packets, reports 200/50 qualified-history shortfalls and creates a manual review worklist; never auto-trains on unverified packets. Separate externally reviewed input can be evaluated locally through the native trainer in an unverified research lane.
- `run_certify` downloads the latest successful original-source and saved SharpAPI research reports, reconciles counts, and lists exact independent-evidence blockers. **This cannot certify missing forecasts or executable odds.**
- `run_health` reports the last observed source capture status; a separate bounded free-source watchdog can retry missed GitHub scheduled runs without making paid bookmaker requests.
- `run_sharp` analyzes saved SharpAPI DraftKings-labeled moneyline quotes and historical line movement from recent successful archive runs; no fresh paid collection and no inference of professional betting flow.
- `run_edge` computes indicative price-vs-model research EV only when real, externally obtained pregame model probabilities and market observations are explicitly supplied through the local CLI; the cloud button defaults to zero rather than fabricating picks.
- `model_status` runs actual native NBA/eight-sport model readiness, safely blocked where independently qualified training evidence is absent.
- Weekly public eight-sport research collection is scheduled best-effort; artifacts expire after 90 days and must be archived for durable historical coverage.
- **No independently validated sports predictions or verified executable sportsbook edge are currently available.** Champion-001 is unchanged and no wagers are placed.

## Control the project from your phone or Windows laptop

**[Open Freddy's Picks AI Phone Command Center](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions/workflows/freddys-command-center.yml)** — choose **Run workflow** on **main**, then select one of the safe actions:

- **status** — latest actual GitHub run status and model-certification holds (no paid calls).
- **all_free_diagnostics** — offline code tests plus public-source capture and research outcome validation.
- **public_eight_sport_scan** — collect original ESPN responses for the eight configured leagues.
- **source_backup** — export tracked source and full Git branch history.
- **nba_live_paid** or **sportsdataio_paid** — optional fresh provider collections; require an additional explicit paid-credit checkbox.

GitHub cloud jobs do **not** require your laptop or phone to stay powered on. A green run means the job completed; it is not independently authenticated model accuracy or bookmaker price proof. View the run Summary and download its artifact.

For all commands, safety controls, mobile browser directions, and PowerShell steps, read [the Phone Command Center guide](FREDDYS_PHONE_COMMAND_CENTER.md).

## Run local integrity tests

Run these from **inside a cloned repository**, not a directory containing only extracted ZIP files:

    git switch main
    git pull --ff-only origin main
    python -m unittest discover -s tests -v

Each PR and each push to main now runs the complete offline validation suite, even for changes to previously uncovered model files. Automatic hourly original-source checks run on GitHub's **best-effort** scheduler. Failed or skipped scheduled events are never assumed successful.

## Model certification remains blocked

- The original Champion-001 executable/source/weights and reproducible reference forecasts are not independently authenticated from connected repos. **Keep Champion-001 frozen.**
- Qualified pregame, point-in-time historical features and independently settled results have not met training/holdout requirements. **No certified Challenger-001 native probability model.**
- Public ESPN schedule matching or SharpAPI-labeled DraftKings odds do not verify executable DraftKings checkout prices.
- Research-only suggestions are not certified positive-EV picks. **No automatic wagers; zero certified bets.**

Track every remaining verifiable blocker in [GitHub issue #41](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/issues/41). Source exports and runs are visible in [GitHub Actions](https://github.com/frederickwalker66-cmyk/Freddy-s-sports-data/actions). The repository's main branch protection must still be enabled by an administrator in Settings → Rules → Rulesets; code alone does not turn it on.
