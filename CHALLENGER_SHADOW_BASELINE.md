# Challenger-001: real pregame $0 shadow baseline (NOT Champion-001)

This is the first **genuine prospective research forecast** step, not the
trained Challenger model and not a certified bet. It addresses a critical
readiness gap: historic game scores and pregame evidence alone cannot yield
a measurable forecast hit rate if no prediction was saved before tipoff.

## Two automated stages

1. The existing `challenger-prospective-pregame.yml` captures ESPN schedule,
   previously published team form, and quarantined aggregator research odds.
   Immediately afterward it runs `challenger_research_shadow_baseline.py`.
   Only *future* events in NBA, MLB, NFL, NHL, NCAAF or NCAAB with enough
   pre-snapshot prior-game evidence produce a $0 forecast. MLS and UEFA
   three-way markets are excluded. The separate immutable-by-artifact
   `research_shadow_forecasts.jsonl` includes both snapshot time and **actual
   forecast creation time**, game ID, and untrained fixed-rule forecast.
2. The existing `challenger-prospective-outcome-validation.yml` later pulls
   archived forecasts and links them to published ESPN final results. It
   runs `challenger_research_shadow_scorecard.py` for *descriptive* Brier
   score, log loss, and classification accuracy per league. Missing or
   duplicate scores, unverified outcomes, identity conflicts, post-tipoff
   timestamps and ineligible markets are rejected or held.

## Important limitations

- **The formula is a predetermined untrained heuristic:**
  `P(home win) = 0.5 + 0.3 × (home prior win rate − away prior win rate)`.
  The win rates are from the prospective evidence snapshot and require three
  to five prior games per side and an assumed 48-hour result delay.
- It is intentionally **not a learned model** and **not a calibrated
  probability**. It never reads sportsbook odds to create the probability.
- NBA/MLB secondary published-score agreements already collected do NOT
  automatically establish historical pregame knowledge or unbiased outcomes.
- Shadow research forecasts are **not Champion-001 predictions**, cannot
  establish certified odds or an expected-value edge, and cannot be used
  as recommendations or stake decisions.
- If the existing GitHub archive lacks forecasts (older runs), the scorecard
  correctly records zero scored games. Future scheduled captures should
  create new prospective forecasts when eligible.
- Below 50 published outcomes per league, even descriptive metrics are
  extremely unstable; meeting 50 alone does not establish calibration.
- ESPN is a published scoreboard source, not independently adjudicated
  settlement. Forecasts need independent source/identity confirmation,
  repeatable out-of-sample evaluation across time windows and **direct
  sportsbook checkout verification** before any betting validation.
- Actions artifacts expire after 90 days. Multi-season evidence still needs
  durable, append-only storage, provenance, and versioned training data.
- This workflow neither places wagers nor trains/replaces Champion-001.
  **All certified Champion-001 and Challenger-001 picks remain zero**.

## Local offline checks

```sh
python -m unittest discover -s tests -v
python challenger_research_shadow_baseline.py --snapshots prospective_pregame/prospective_event_evidence.jsonl --output-dir prospective_pregame
python challenger_research_shadow_scorecard.py --forecast-root snapshots --linked-results prospective_validation/linked_pregame_outcomes.jsonl --output-dir prospective_validation
```

### Real next advancement

Use these actual time-stamped research forecasts to establish an outcome-linked
track record. In parallel, collect independently audited pregame feature and
outcome records and use rolling-origin validation to train a **separate**
Challenger-001 model. Compare against 50% and no-vig price baselines with
Brier, log loss, confidence intervals and calibration diagnostics. Keep
Champion-001 frozen during research.
