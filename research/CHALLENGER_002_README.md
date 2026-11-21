# Challenger-002 — isolated research lane

This is a **new** model, not a recovered Champion-001. Original Champion-001 remains frozen and unchanged. Do not rename Challenger-002 to Champion-002 without independently documented validation and approval.

## Initial implementation
`python -m research.challenger_002_baseline --input point_in_time_examples.jsonl --output artifacts/challenger_002_research.json`

Each JSONL record must have `event_id`, `event_start_at`, `observed_at`, `outcome_observed_at` (timezone-aware ISO timestamps; outcome timestamp must be after event start), `outcome` (0/1), and `features` (same numeric feature names on every record). Each row represents a **binary target** and must have a unique event ID for that target; use separate datasets per market. Features must be point-in-time, and settled outcomes must be independently verified. The current script checks timestamps and schema but **cannot prove** that the underlying feature values were genuinely available at the recorded time.

Minimum initial research gate: 200 training rows and 50 later testing rows. Chronological holdout; train features **and recorded outcome availability** must predate the first test event. No fabricated historical data, no model probability substitutions, and no sportsbook-implied probabilities as training targets.

Run offline checks: `python -m unittest tests.test_challenger_002_baseline` (tests must pass before merging).\n\n## Explicitly NOT implemented or certified
- No production deployment, no live SportsDataIO or DraftKings ingestion.
- No authenticated odds, injuries, roster verification, or player props feed.
- No independent data provenance, model calibration signoff, market-specific holdout certification, or release signature.
- No Certified TAKE, no staking, and no modification to Champion-001 or existing certification gates.

The output always contains `certified_take_count: 0`. Passing research metrics is not certification. Later phases must add source-backed point-in-time ingestion, per-market features, disjoint calibration and test windows, signing, verification, and production controls through separate reviewed changes.

## Manual authenticated NBA snapshot workflow

GitHub Actions: `.github/workflows/challenger-002-nba-snapshot.yml` (workflow_dispatch only). Select a date and `nba_scores` or `nba_odds`. Credentials are read from GitHub Actions secrets `SPORTSDATAIO_NBA_API_KEY`, `SPORTSDATAIO_ODDS_API_KEY`, or existing `SPORTSDATAIO`. No credentials should be pasted into issues or logs.

This workflow makes an authenticated request through the existing trusted provider gateway, writes the licensed canonical response to an ephemeral runner directory, and uploads **metadata only** (status, count, digest, time). It does not upload raw licensed provider data. Because the ephemeral data is not retained, it cannot itself populate the training dataset or establish historical point-in-time custody. Source licensing and a secure retention design must be reviewed before persisting data. The workflow has not been executed merely by committing it.
