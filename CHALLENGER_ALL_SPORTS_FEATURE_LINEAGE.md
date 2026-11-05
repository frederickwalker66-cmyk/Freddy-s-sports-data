# Freddy's Picks AI: all-eight-sport prospective feature lineage

## Purpose

The highest-priority shared model-development gap is independent point-in-time
provenance for genuine pregame inputs, not more untrained betting picks.
This module makes **as-observed research lineage auditable** for NBA, NFL,
MLB, NHL, NCAAF, NCAAB, MLS and UEFA Champions League.

In `historical_outcomes.collect`, previously all returned score records were
stamped with the time the *entire collection began*, before any HTTP response.
That could misstate when later replies became observable. The collector now
stamps each successful response **after receipt**, with a distinct
`retrieved_at_utc` timestamp that can differ across requests/leagues.
It rejects a non-timezone-aware or backward receipt clock.

The new `challenger_all_sports_feature_lineage.py` checks **each genuinely
captured future-game team form** against the parsed prior game results in the
same archived run. It requires matching source league, ESPN IDs, team,
season (NBA regular season), recorded scores, source URL, receipt timestamp,
48-hour pregame embargo, unique games and exact numeric form reconstruction.
It keeps the original underlying parsed rows' time and a self-issued SHA-256
for future reviewer reconciliation.

Output is stored under
`prospective_pregame/feature_lineage/feature_lineage.jsonl` and
`feature_lineage_report.json`, embedded in the **existing** 90-day prospective
GitHub Actions artifact after the morning/evening capture. Empty/no-game
leagues remain represented without invented events.

## Evidence limits

- These are **parsed ESPN-public-scoreboard observations**, not independent
  league settlement, original signed scoreboard publication, or an immutable
  external timestamp witness. An observed-at time and SHA establish only
  provenance inside this run. The module explicitly reports
  `original_scoreboard_bytes_preserved_by_this_stage: false`.
- Previous historical game scores observed *today* may support **future**
  features captured today, but cannot retroactively prove what would have
  been available before an older game.
- Team form is **not a native model forecast**. No input row is marked
  independently qualified for training or calibration. Odds implied
  probabilities are never used.
- MLS and UCL knockout final scores are **not** certified standard 90-minute
  market outcomes. Separate 3-way models/settlements remain required.
- This does not train a model, certify 25-50 shadow picks, approve DraftKings
  checkout, clear player props, or place money.
- Champion-001 remains frozen. No extra cron or SportsGameOdds collection is
  enabled. The legacy active SportsGameOdds file-import option was removed
  from the prospective capture.

## Offline checks

```bash
python -m unittest discover -s tests -p 'test_challenger_prospective_pregame.py' -v
python -m unittest discover -s tests -p 'test_historical_source_receipt_timing.py' -v
```

Run this on any existing same-run source bundle:

```bash
python challenger_all_sports_feature_lineage.py \
  --events prospective_pregame/prospective_event_evidence.jsonl \
  --historical prospective_pregame/historical_published_results.jsonl \
  --output-dir prospective_pregame/feature_lineage
```

## Next required data milestone

Preserve actual **original response bytes** and external source-publication
observations, independently review past feature availability, obtain historical
league-specific target settlement, construct 200 genuine earlier training and
50 later disjoint evaluation examples for each league/market, then produce real
out-of-sample native Challenger predictions. Only **after** those exist can
isotonic calibrators be fitted. Odds and game-winner models do not establish
player-prop probabilities.
