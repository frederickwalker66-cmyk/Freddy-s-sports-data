# Challenger-002 — isolated research lane

This is a **new** model, not a recovered Champion-001. Original Champion-001 remains frozen and unchanged. Do not rename Challenger-002 to Champion-002 without independently documented validation and approval.

## Initial implementation
`python -m research.challenger_002_baseline --input point_in_time_examples.jsonl --output artifacts/challenger_002_research.json`

Each JSONL record must have `event_id`, `event_start_at`, `observed_at` (timezone-aware ISO timestamps), `outcome` (0/1), and `features` (same numeric feature names on every record). Each row represents a **binary target** and must have a unique event ID for that target; use separate datasets per market. Features must be point-in-time, and settled outcomes must be independently verified. The current script checks timestamps and schema but **cannot prove** that the underlying feature values were genuinely available at the recorded time.

Minimum initial research gate: 200 training rows and 50 later testing rows. Chronological holdout; train observations must predate the first test event. No fabricated historical data, no model probability substitutions, and no sportsbook-implied probabilities as training targets.

## Explicitly NOT implemented or certified
- No production deployment, no live SportsDataIO or DraftKings ingestion.
- No authenticated odds, injuries, roster verification, or player props feed.
- No independent data provenance, model calibration signoff, market-specific holdout certification, or release signature.
- No Certified TAKE, no staking, and no modification to Champion-001 or existing certification gates.

The output always contains `certified_take_count: 0`. Passing research metrics is not certification. Later phases must add source-backed point-in-time ingestion, per-market features, disjoint calibration and test windows, signing, verification, and production controls through separate reviewed changes.
