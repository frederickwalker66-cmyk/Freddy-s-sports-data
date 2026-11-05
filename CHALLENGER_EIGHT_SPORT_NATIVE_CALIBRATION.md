# Freddy's Picks AI — eight-sport native probability and calibration evidence gates

Status: **RESEARCH ONLY, not calibrated, no positive-EV certification, no automatic wagers**.
Frozen Champion-001 remains completely unchanged.

## Supported sports and settlements

| League | Native outcome categories | Market definition |
|---|---|---|
| NBA | Home, away | Full-game winner including OT. **Handled by existing** `challenger_native_pregame_capture.py` |
| NFL | Home, away | Full-game winner including OT |
| MLB | Home, away | Full-game winner including extra innings |
| NHL | Home, away | Full-game winner including OT/shootout |
| NCAAF | Home, away | Full-game winner including OT |
| NCAAB | Home, away | Full-game winner including OT |
| MLS | Home, draw, away | Three-way **90-minute regulation + stoppage time** |
| UEFA Champions League | Home, draw, away | Three-way **90-minute regulation + stoppage time**, not extra time/penalty outcome |

There are **no player-prop models** in this new gate. Moneyline probability
cannot be recycled to price points, rebounds, assists, goals, shots, or other
player props. Soccer draws are distinct from either team's win probability.

## New prospective probability receipt stage

`challenger_multisport_native_capture.py` runs in the existing prospective
research workflow after the specialist NBA receipt capture. It reads three
separate inputs:

- Same-run genuine `prospective_pregame/prospective_event_evidence.jsonl`.
- `prospective_pregame/multisport_game_candidates.jsonl` with real, fresh
  league-specific features and availability evidence.
- `challenger_results/multisport_models/<league>.json` for each non-NBA
  league, containing the previously trained research model artifact.

**None of the seven non-NBA model artifacts or current model-feature candidate
files are supplied by the repository today.** Without them the step succeeds
with a transparent **blocked** report, never creating artificial probabilities.

The model format is a deterministic research-only scorer, *not a trainer*:

```json
{
  "league": "nfl",
  "market_type": "moneyline",
  "settlement_scope": "including_overtime",
  "lane": "Challenger-001",
  "status": "unverified_research_model_not_deployed",
  "model_version": "challenger-001-nfl-native-v1",
  "trained_at_utc": "2026-11-01T00:00:00+00:00",
  "chronological_training_rows": 200,
  "later_holdout_rows": 50,
  "historical_source_evidence_sha256": "64 lowercase hex characters",
  "feature_names": ["pregame_away_form", "pregame_home_form"],
  "feature_means": [0.5, 0.5],
  "feature_stds": [0.2, 0.2],
  "binary_logistic_coefficients": [0.0, -0.4, 0.4],
  "qualified_for_real_money_wagers": false,
  "calibration_independently_certified": false,
  "champion_001_modified": false,
  "artifact_sha256": "SHA256 over canonical JSON of every field except artifact_sha256"
}
```

This is **a schema example only**, not a real trained NFL artifact or
evidence of existing validation. Never fabricate file contents or training
counters to activate the scorer.

For soccer models, the `market_type` is `three_way_result`, the
`settlement_scope` is `regulation_90_minutes_including_stoppage`, and
`three_way_softmax_coefficients` replaces `binary_logistic_coefficients`.
It contains distinct coefficient vectors for `home`, `draw`, and `away`.
The three resulting probabilities are normalized to sum to 1. Exact data
schema must match the trained model and the same pregame ESPN schedule.

The capture module checks model SHA integrity, league/version/market identity,
minimum historical train and later holdout counters, exact game identity,
team names, future kickoff, source URLs, pregame feature timing, injury/status
review within two hours, and prediction probability validity. These checks
cannot establish **independent** provenance solely from self-supplied flags or
SHA values. No deployment, wagering, or model training occurs.

Run:

```bash
python challenger_multisport_native_capture.py \
  --snapshots prospective_pregame/prospective_event_evidence.jsonl \
  --candidates prospective_pregame/multisport_game_candidates.jsonl \
  --model-dir challenger_results/multisport_models \
  --output-dir prospective_pregame
```

The output is `native_multisport_forecasts.jsonl` (usually empty, until
models and candidates qualify) and `multisport_native_capture_report.json`.
All selection receipts are uncertified, $0 research only.

## Outcome evidence and calibration review

The daily calibration job reuses existing GitHub Actions archives and runs
`challenger_multisport_calibration_review.py` to match intact binary or
three-way probability vectors to ESPN-published finals. It creates only
`multisport_review_queue.jsonl` and `multisport_review_report.json`.
The soccer result cannot be graded as a regulation-time market settlement
without **separate** explicit adjudication of the 90-minute match state.

**Critically, the bridge does not produce `challenger_oos_probabilities.jsonl`
or any independently verified/calibration-eligible label.** The existing
isotonic calibration stays blocked until authentic native pregame forecasts,
verified final/market outcomes and at least 200 earlier + 50 later events
exist **for the same league, market, side and model version**, with disjoint
chronological calibration and test partitions. No claim of 100% prediction
accuracy, certified ROI, or verified EV is made.

## Testing

```bash
python -m unittest discover -s tests -p 'test_challenger_multisport_native_capture.py' -v
python -m unittest discover -s tests -p 'test_challenger_multisport_calibration_review.py' -v
python -m unittest discover -s tests -v
```

Next dependency: independently construct *actual* verifiable historical
point-in-time features/outcomes by sport, train the separate native league
models, and preserve immutable pregame predictions. The infrastructure must
fail closed without those dependencies.
