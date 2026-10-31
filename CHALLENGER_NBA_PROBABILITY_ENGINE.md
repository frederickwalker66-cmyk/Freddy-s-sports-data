# Challenger-001 NBA moneyline probability engine v1

Status: **research-only, not a certified model, not deployed, not a pick generator.**
Champion-001 remains frozen and separate.

## What was built

`challenger_nba_probability.py` fits a deterministic ridge-regularized logistic
regression for **NBA home-team moneyline probability** using independently
constructed, source-reviewed pregame numeric features. Feature scaling, base
rates, and coefficients are learned exclusively on the training partition.

For evaluation, games are split chronologically with entire event dates held
together. Prior training outcomes must have been verified before the earliest
holdout snapshot. The output includes Brier score, log loss, a training-rate
baseline, accuracy at the 0.5 threshold, and exploratory calibration bins.
After reporting the holdout result, the tool optionally refits on all already
settled eligible games; **the holdout metrics do not evaluate that refitted
final artifact.** Forward testing is still needed.

Artifacts contain training-time metadata, feature schema, weights, scaler,
source-evidence digest, and an integrity fingerprint. The latter detects
accidental changes, **not** malicious signed-source tampering or fabricated
training data. All saved data should still be independently audited.

## Historical input requirements

The CLI accepts `historical_results.jsonl`, one *home perspective* NBA
full-game binary moneyline example per event, plus these existing backtest
fields:

- `event_id`, `league: "nba"`, `market_type: "moneyline"`,
  `selection_type: "home"`, `outcome: 0|1`
- `snapshot_utc`, `features_asof_utc`, `start_utc`, and
  `outcome_verified_at_utc` with explicit timezone offsets
- `event_source_url`, `feature_source_url`, and `outcome_source_url`
- `features`: 1–12 numeric `pregame_*` values, same schema across all games.
  Do not include odds, implied probabilities, final scores, outcomes, or
  information not verifiably available as of the snapshot.

Extra **research intake attestation** fields are required:

- `qualified_for_challenger_backtest: true`
- `independent_asof_review: true`
- `independent_outcome_review: true`
- `feature_snapshot_sha256` and `outcome_snapshot_sha256`: lowercase SHA-256
  digests of independently archived source receipts.

**Important:** A boolean review flag, a plausible HTTPS URL, and a hash are
metadata; they are not independently validated evidence. The script does not
retrieve or verify upstream receipts. The proposed dataset must be reviewed
by an independent process before claiming authenticity. Synthetic fixture
rows in the tests are intentionally false as real-world records.

The default fit requires at least **200 eligible training games** and
**50 later disjoint holdout games**, with both result classes. It will block
if the review-attested, settled data is absent, schema-inconsistent, temporally
invalid, or insufficient. These thresholds are development requirements,
not statistical proof of profitable betting.

## Execution

```bash
python -m unittest discover -s tests -v
python challenger_nba_probability.py --history historical_results.jsonl \
    --output-dir challenger_results/nba_probability
```

With insufficient or absent evidence, the tool writes only
`report.json` with `blocked_no_qualified_nba_training_data` and
**does not** create `research_model.json`.

A future candidate may be scored only in the same explicitly research-only
CLI run using `--candidate future_event.json`, and only if a genuine trained
model is available. It must have a future event start, an actually current
pregame snapshot, model-trained time not later than snapshot time, identical
features, and source/injury review attestations with an availability check
no more than two hours before snapshot. There is no replay/backfilling
of past games as supposedly pregame forecasts.

Forecasts explicitly remain uncertified, paper stake $0, not eligible for
the certified Champion-001 ledger, and have no implied bet recommendation.
Sportsbook prices are never used to compute the research model probability.

## Still missing

1. Sufficient authentic *point-in-time* NBA data and independent source-receipt
   verification—not retroactive final-score-derived feature claims.
2. Multiple rolling-origin seasons and an untouched prospective holdout;
   reliability/calibration checks and uncertainty intervals.
3. Real player injury/lineup ingestion with provider ID reconciliation,
   provenance checks and verified direct sportsbook quotes.
4. A separate player-prop count/distribution model; this moneyline model
   must not be recycled as a player-points or assists forecast.
5. Independent review and explicit user approval before any future production
   deployment. Absolutely no automatic wager placement.

Passing CI proves software fixtures passed, not that a model was trained on
genuine games or achieved better than market profitability.
