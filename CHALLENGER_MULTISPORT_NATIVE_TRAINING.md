# Challenger-001 native training — seven non-NBA game markets

Status: **implemented as an isolated research-only training stage; no certified models or bets.** NBA retains its existing specialist probability engine. Champion-001 is not accessed or modified.

## Sports and target definition

The new trainer supports binary full-game home/away winner for NFL, MLB, NHL, NCAAF and NCAAB, and separate **home/draw/away** 90-minute regulation (including stoppage) for MLS and UEFA Champions League. It never trains player props, spreads, totals, alternate lines, or same-game parlay correlations.

The pipeline reads manually reviewed, genuine pregame feature + independently adjudicated settlement evidence. Existing retrospective ESPN published-score archives, automatic review queues, market-implied odds, and self-issued hashes do **not** qualify by themselves. Any review flags and source URLs supplied in a row still require real, externally supported human/source provenance verification before they can be trusted.

## Schema and checks

Each row in `challenger_reviewed_pregame_games.jsonl` must include:
- `record_type: challenger_reviewed_pregame_game_evidence_v1`
- `league`, `event_id` (ESPN ID string), exact `market_type` and `settlement_scope` from `challenger_multisport_native_capture.py`
- `start_utc`, `snapshot_utc`, `features_asof_utc`, `outcome_verified_at_utc` as UTC timestamps with offsets
- `features`: 1–12 finite numeric keys starting `pregame_` only; same names across each league
- `outcome`: home/away; additionally draw for MLS and UCL
- `event_source_url`, `feature_source_url`, `outcome_source_url` (HTTPS)
- `feature_snapshot_sha256`, `outcome_snapshot_sha256` as original 64-hex evidence receipt digests
- `independent_feature_asof_review: true`, `independent_outcome_review: true`, `market_settlement_rules_verified: true`
- `qualified_for_challenger_training: true`, `champion_001_modified: false`

The software **cannot independently validate authenticity merely by seeing those booleans, URLs or SHA hashes**. Never generate affirmative review flags from the automatic ESPN review queues. The trainer rejects duplicates, unavailable or late outcome labels, post-kickoff feature timestamps, non-game markets, mixed feature schemas, and missing review evidence.

Minimum **per league**: 200 earlier training observations and 50 later same-league holdout observations. Results not verified by the first holdout's pregame snapshot are excluded from training. Both Brier score and log loss must improve over a training-only class-frequency prior on the chronological holdout before creating an unverified research artifact. The model is refit using the now-settled record set; the reported holdout metrics refer to the earlier fit, not that refit.

The model artifacts use exactly the native game scorer's schema and can be placed into `challenger_results/multisport_models/<league>.json` **only after separate operational evidence inspection**. They are not calibrated or wager-certified and have no production promotions.

## Commands

```bash
python -m pip install -r requirements-calibration.txt
python -m unittest discover -s tests -p 'test_challenger_multisport_native_training.py' -v

python challenger_multisport_native_training.py \
  --evidence challenger_reviewed_pregame_games.jsonl \
  --output-dir challenger_results/native_model_training
```

For a safe absence-of-data diagnostic:

```bash
python challenger_multisport_native_training.py \
  --evidence challenger_reviewed_pregame_games.jsonl \
  --output-dir challenger_results/native_model_training \
  --allow-missing-evidence
```

This creates only `research_training_report.json` when no real reviewed evidence exists. It does not invent games, install a model or create predictions. The training stage never calls any sportsbook or data-provider API.

**Next external dependency:** point-in-time team statistics, independently authenticated original pregame snapshots, and independently verified game/90-minute outcome settlements for 250+ chronological events **per league**. Player-prop modeling requires separate per-player as-of box scores and availability data. Calibration needs additional genuine OOS pregame forecast receipts beyond the training holdout.

Safety invariants: `champion_001_modified=false`, `certified_champion_001_predictions=0`, `certified_challenger_001_predictions=0`, `certified_positive_ev_bets=0`, `automated_bets_placed=0`.
