# Freddy's Sharp Edge Pro — independent platform staging

This directory stages a separate betting research and prediction platform. It does not import Champion-001 predictions or modify the frozen model.

## Operating contract
- Providers: reuse authorized SportsDataIO and SharpAPI credentials through GitHub Actions secrets; never store keys in the repository or public dashboard.
- Five-minute cadence: free readiness/validation checks; live paid API polling must be enabled only after provider limits and recurring spend are confirmed.
- Outputs: RESEARCH, WATCH, HOLD; TAKE only after independent calibrated model probabilities, verified sportsbook price, roster/injury provenance, and time-stamped backtest/shadow results pass policy gates.
- Shadow stakes: $0. Never automatically place wagers.
- Independent engine: train and version a new Sharp Edge Pro model separately from Champion-001, with reproducible train/test time splits and calibration.
- Manual betting only: user decides and submits any wager outside the platform.

## Current status
STAGING ONLY. No new model trained; no production prediction service; no live credentials tested. This folder is not an independent GitHub repository or deployed website.
