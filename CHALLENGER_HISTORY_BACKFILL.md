# Challenger-001 — faster, capped historical score research

**Purpose:** Expand published historical outcomes across NBA, NHL, MLB, NFL,
college football and college basketball using existing public ESPN scoreboard
code. It makes **zero SharpAPI, Sports Game Odds, or DraftKings requests**.
Champion-001 is frozen.

## How the faster stage runs

The separate workflow `.github/workflows/challenger-historical-backfill.yml`
has six league-specific jobs with **at most two concurrent jobs**. Each
downloads **one fixed 35-day in-season window**, so the entire run attempts
at most **210 public ESPN scoreboard day requests**. On a pull request it
runs offline safety tests only. A merge to main triggers the six-league
historical collection once; it can also be dispatched manually.

For each league, GitHub saves separate JSONL and JSON research artifacts for
30 days. No market odds, API credentials, or real-money action are needed.

To validate without making requests:

```bash
python challenger_historical_backfill.py --league nba --dry-run
python -m unittest discover -s tests -v
```

To collect a bounded historical window:

```bash
python challenger_historical_backfill.py --league nba --days 35 --output-dir challenger_backfill
```

### What is—and isn't—validated

- Published results: **independent public ESPN scoreboard evidence, not
  official league adjudication**.
- Candidate features: retrospective five-game form derived from published
  final scores, with an **assumed** 48-hour result embargo; this is **not a
  verified historical pregame timestamp**.
- Every candidate remains `qualified_for_challenger_backtest=false`,
  `historical_odds_snapshot_verified=false`, and `bet_ready=false`.
- Every batch records attempted, successful and failed source days.
  `coverage_complete=false` if *any* daily request failed. Do not infer
  complete coverage from a partial archive.
- No one should rename these candidates to `historical_results.jsonl`
  or use exploratory scores as certified model probabilities.
- Historical outcomes, lineup availability, actual feature publication
  times, and odds checkout still need independently verified provenance.
- The separate Champion-001 remains frozen; certified Champion and
  Challenger bets and automated wagers remain zero.

**Next real milestone:** expand to audited, continuous season-long pregame
feature/outcome evidence (not just isolated windows), then evaluate
Challenger-001 with time-ordered out-of-sample backtesting and calibration
against properly timestamped odds.
