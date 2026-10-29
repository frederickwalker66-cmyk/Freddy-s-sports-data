# Challenger-001 — historical validation stage (research-only)

This is a **separate baseline backtest**, not the user's frozen Champion-001
model, and it never uses sportsbook implied probability as a model forecast.
It does not place bets, certify odds, or recommend wagers.

## What exists

- `challenger_backtest.py`: isolated logistic-regression *research baseline*
  with a chronological 80%/20% holdout, per-league partitions, training-only
  feature scaling, and results restricted to those verified **before** the
  first holdout observation.
- `tests/test_challenger_backtest.py`: synthetic tests, including future-outcome
  leakage, unsupported markets, duplicate games, and blocked-data behavior.
- `.github/workflows/challenger-backtest.yml`: no-key offline CI, produces
  `challenger_results/backtest_report.json`.

## Historical data is not in this repository

Odds snapshots from SharpAPI and Sports Game Odds are **not** independently
labeled historical outcomes or verified pregame predictive features. They must
not be silently converted into training labels or substituted for a forecaster.

Without a genuine `historical_results.jsonl` input, the workflow reports
`blocked_no_qualified_historical_data`. CI passing does **not** mean a
prediction system has been trained.

## Required input: historical_results.jsonl

One JSON object per line, exactly **one candidate moneyline side per game**.
Required fields:

- `event_id`, `league`, `market_type: "moneyline"`,
  `selection_type: "home" | "away"`
- `snapshot_utc` when prediction inputs would have been available
- `features_asof_utc` timestamp no later than `snapshot_utc`
- `start_utc` later than `snapshot_utc`
- `outcome_verified_at_utc` later than the event start
- `event_source_url`, `outcome_source_url`, `feature_source_url`
  (HTTPS evidence links **do not establish actual verification**)
- `outcome: 0 | 1` for that selected moneyline side
- `features`: one to twelve independently sourced numeric `pregame_*`
  indicators; no odds, implied probability, final scores or outcomes.

Only binary-moneyline leagues NBA, NFL, MLB, NHL, NCAAF, NCAAB, WNBA are
eligible for this initial stage. Soccer 3-way moneylines, ties, player props,
spreads and totals need distinct settlement and predictor modules.

Default acceptance threshold is **200 training examples and 50 holdout
examples per league**, with both outcome classes represented and training
results known by the first test snapshot. Too little data means blocked.

Run offline:

```bash
python -m unittest discover -s tests -v
python challenger_backtest.py --input historical_results.jsonl --output challenger_results/backtest_report.json
```

The output's Brier, log loss and accuracy values are **uncertified offline
metrics**. This first holdout is only a development baseline; it is not
walk-forward validation across many seasons. Before promoting any model,
independently verify source provenance, assemble multiple rolling-origin
seasons, evaluate calibration versus a no-vig market baseline, account for
vig and price movement, verify player availability and genuine available
checkout odds, and demonstrate stable out-of-sample value. Keep the original
Champion-001 frozen and shadow wager amount at $0 pending validation.
