# Challenger-001 isotonic recalibration (research only)

`challenger_isotonic_recalibration.py` **fits** an independent per-market isotonic
calibrator using native out-of-sample Challenger probability forecasts paired
with subsequently verified WIN/LOSS results. This is different from the existing
`challenger_oos_calibration.py`, which **scores** holdout predictions but does
not fit a probability remapping.

**Nothing here changes or accesses Champion-001.** This is not a sportsbook
implied-probability converter, player-prop prediction engine, certified EV
solver, or betting system. No wager is placed or approved by this workflow.

## Daily workflow

`.github/workflows/challenger-isotonic-calibration.yml` runs daily at **11:17
UTC** (6:17 AM EST / 7:17 AM EDT), on demand, and in CI when calibration code
changes. It installs scikit-learn, runs synthetic tests, and writes a machine-
readable research report as a GitHub Actions artifact.

The repository does **not** currently include
`challenger_oos_probabilities.jsonl`, so the scheduled job **reports
`blocked_missing_prediction_evidence_file`** and saves **no calibrator**.
This is expected and safe. A completed workflow is not proof of successful
model calibration. Do not create synthetic production rows to bypass this.

## Requirements

```bash
python -m pip install -r requirements-calibration.txt
python -m unittest discover -s tests -p 'test_challenger_isotonic_recalibration.py' -v
python challenger_isotonic_recalibration.py \
  --evidence challenger_oos_probabilities.jsonl \
  --output-dir challenger_results/isotonic_recalibration \
  --allow-missing-evidence
```

The report is at `challenger_results/isotonic_recalibration/report.json`.
The command without `--allow-missing-evidence` exits with code 2 when the file
is absent. The flag is only for daily fail-closed reporting, not for inventing
missing probabilities.

## Validated evidence format (one JSON object per line)

Each row represents one **uniquely identified binary selection** (for player
props include event, player, market, line and side in `event_id`).

- `league`: `nba`, `nfl`, etc.
- `market_type`: `moneyline`, `player_points`, `player_assists`, `player_pra`, etc.
- `selection_key`: `home`, `away`, `over`, `under` (do not mix outcome definitions)
- `model_version`: version of the **actual native Challenger forecast**;
  must begin `challenger-`
- `probability_source`: literally `native_challenger_model`
- `model_probability`: float strictly between 0 and 1; not implied from odds
- `event_id`: stable identity, unique per league, market, selection and version
- `prediction_timestamp_utc`, `event_start_utc`, `outcome_verified_at_utc`:
  time-zone-aware ISO 8601 timestamps, with forecast < event < verification
- `settlement`: `WIN` or `LOSS`. Exclude push, void, missing and unsettled
- `champion_001_modified`: `false`
- Evidence review flags, all `true`: `independent_outcome_verified`,
  `historical_pregame_features_verified`, `model_output_before_event_verified`,
  `chronological_holdout`, `model_training_excludes_holdout`,
  `independent_pregame_receipt_verified`

**Crucial:** These flags are assertions. The script does not independently
inspect external receipts or prove their authenticity. Genuine model forecasts
must be recorded **before** the relevant games and their outcomes verified
*after* game completion. No sportsbook break-even percentage may be used as a
stand-in for a model probability. The present NBA home-moneyline model is not
a player-prop predictor.

## Method

1. Segment by exact league/market/selection/version; reject mixed datasets.
2. Keep only settled pregame OOS native probabilities with review attestations.
3. Split on complete UTC event dates into earlier calibration and later test.
4. Exclude any earlier result not actually known before the first test
   prediction was captured (prevents future-outcome leakage).
5. Fit an isotonic monotone mapping using a minimum of **200** earlier
   predictions. Compare raw vs transformed scores on at least **50** later
   untouched predictions, each period with wins and losses.
6. Save a research-only artifact **only if** Brier score **and** log loss
   improve; compare reliability bins and ECE for additional context.
7. Preserve holdout results as evaluation-only; do not promote a calibrator
   to production without an additional untouched prospective evaluation.

The output `knots_x`/`knots_y` is an integrity-hashed, research-only mapping.
A local Python call for a matching segment is:

```python
from challenger_isotonic_recalibration import apply_research_calibrator
import json

artifact = json.load(open('challenger_results/isotonic_recalibration/<artifact-filename>.json'))
calibrated = apply_research_calibrator(
    artifact, 0.58,
    league='nba', market_type='moneyline', selection_key='home',
    model_version='challenger-001-nba-home-moneyline-v1',
)
print('Research-only calibrated probability:', calibrated)
```

The above 0.58 is a **demonstration input**, not a real Freddy's Picks AI
probability. A saved mapping never certifies a bet or authenticates its sources.

## Next dependency

Implement independent provenance of historical *native* Challenger OOS
forecasts and settled outcomes (minimum 250 distinct observations per segment,
chronological split and no training contamination). The existing repository's
`challenger_oos_calibration.py` and historical-review gates must still pass.
The daily job stays blocked without authentic data.