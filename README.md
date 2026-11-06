# Freddy's Picks AI — All-Sports Research and GitHub Control Center

**This repository contains a research-only sports evidence pipeline and automated GitHub workflows. It is not yet an independently certified real-money betting prediction engine.**

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
