# Challenger-001 — historical pregame feature candidates (not training-ready)

## Purpose

This is a new, separate **quarantined research stage**. It creates possible pregame features from previous published ESPN game results, using the historical data already archived by `historical_outcomes.py`. It **does not** create or overwrite `historical_results.jsonl`, update Champion-001, train a production model, check current odds, or certify any bets.

Run after historical collection:

```bash
python historical_outcomes.py --days 21 --output-dir challenger_history
python challenger_feature_candidates.py --results challenger_history/results.jsonl --output-dir challenger_history
```

Outputs in the historical artifact:
- `feature_candidates.jsonl`: one home-side research candidate per settled binary-moneyline game, with team Elo differential, prior game counts and smoothed prior win rates.
- `feature_coverage.json`: league coverage, exclusions and **zero verified training examples**.

The features are generated chronologically, with previous game outcomes held back for a **minimum assumed 48-hour delay** after each earlier event's start. This prevents nearby/same-day results from contaminating older snapshots. It is **not** evidence of actual historical final publication time. Team ratings and rates are research baselines, not calibrated predictions.

Only NBA, NFL, MLB, NHL, NCAAF and NCAAB binary-moneyline candidates are included at this stage. Ties and three-way soccer results are excluded. Player props and spreads have no matching settlement model here.

## Promotion gate — still blocked

The candidate records deliberately set `training_eligible=false`, `historical_feature_availability_verified=false`, `official_outcome_verified=false`, `bet_ready=false`. There is no direct DraftKings verification. Source URLs alone do not independently verify evidence.

Before any candidate may become a qualified row in `historical_results.jsonl`, obtain and audit:

1. Event identity, winner/settlement against independent authoritative results.
2. Historical availability timestamps for every predictive feature; source provenance and complete data coverage (not merely a URL or today's retrieval).
3. Real pregame lineup, injury and roster information where used, with documented as-of dates.
4. Season-spanning training and chronologically separate test windows with no future leakage; minimum 200 train and 50 holdout examples **per league** is only the first software gate, not model validation.
5. Genuine sportsbook checkout price verification before any live EV claims.

Do not use market-implied probabilities as the model forecast. Assess Brier score, log loss, calibration and baselines before accepting a Challenger result. Keep Champion-001 frozen, daily certified picks at **zero** unless they are genuinely produced by that frozen model, and shadow stakes at $0 during validation.

See [CHALLENGER_BACKTEST.md](CHALLENGER_BACKTEST.md) for the different, strict input schema required by the offline logistic backtest.
