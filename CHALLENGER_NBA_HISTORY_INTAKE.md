# Challenger-001 NBA Historical Intake Review

Status: **research-only; no independent training provenance established**.

## Input and outputs

This stage reads the *existing* eight-sport pregame-to-result review queue,
which comes from actual archived prospective event observations and later
ESPN-published final scores. It does not call SportsGameOdds, SharpAPI or any
other sportsbook service.

```bash
python challenger_nba_history_intake.py \
  --review-queue prospective_validation/all_sports_evidence_review_queue.jsonl \
  --output-dir prospective_validation
```

The stage creates:
- `nba_history_review_candidates.jsonl` — only structurally valid NBA home
  perspective published-score research rows, with every training/review flag
  **false**. This file is **NOT** `historical_results.jsonl`.
- `nba_history_intake_report.json` — source coverage and per-event blockers,
  non-NBA exclusions, duplicates quarantined, and the shortfall to the
  **200 chronological training + 50 later holdout game** development target.

It rejects contradictory outcome labels, ties (incompatible with NBA binary
full-game winner), missing or future/out-of-order timestamps, unrecognized
source URLs, unfit four-feature snapshots, duplicate event IDs and any
surprisingly promoted research/certification flag. Missing original evidence
is reported, not filled with assumptions.

## Independent verification still needed BEFORE any training

1. Recover original archived pregame feature snapshots and the source page/
   feed version actually available at each timestamp; verify publication time
   independently of the collecting workflow's self-reported clock.
2. Corroborate final score, league event identity, dates and full-game
   overtime settlement against an independent outcome source.
3. Validate original source bytes and receipts with an independent provenance
   mechanism. The internal SHA-256 receipts alone cannot prove authenticity.
4. Audit team ID crosswalk, roster status, sample season, and the pregame
   feature calculation. Avoid any lookahead (including final-score data from
   later games in the prior-form window).
5. Only after independent reviewer signoff create separate qualified training
   input with positive audit records and real, independently checked receipt
   digests. Neither this stage nor ordinary synthetic tests can sign it off.
6. Fit and evaluate the existing Challenger NBA moneyline engine using
   chronological non-overlapping train/test periods, then prospective shadow
   test; keep any model artifact research-only until further authorization.

## Production and betting isolation

Champion-001 remains unchanged. This stage does not create a probability model,
betting line, model prediction, +EV recommendation or real-money bet. It cannot
move any research candidate to a qualified training file on its own. A passing
software test is evidence of correct fixture behavior, not model calibration
or profitability.
