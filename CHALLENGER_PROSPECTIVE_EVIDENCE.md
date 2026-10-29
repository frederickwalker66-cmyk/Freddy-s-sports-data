# Challenger-001 — prospective eight-league evidence capture

This new stage advances the eight-league historical readiness audit by capturing
**real point-in-time research observations before upcoming games**, rather than
relabeling October 2026 archived results as February 2026 pregame knowledge.

## Where it runs

`.github/workflows/challenger-prospective-pregame.yml`:
on pull requests, runs **offline safety tests only**. When merged to `main`,
manually dispatched, or triggered by GitHub's **13:15 and 20:15 UTC daily**
cron schedule (subject to GitHub queue delays), it can:

1. Read the latest successful **existing** SharpAPI DraftKings-labeled odds
   artifact, SportsGameOdds artifact, and official NBA/MLB evidence artifact.
   Missing artifacts are reported as gaps, not silently filled. It does not
   call the paid sports odds APIs directly or consume their credits.
2. Fetch **today's** pregame public ESPN schedules for NBA, NFL, MLB, NHL,
   NCAAF, NCAAB, MLS and UEFA Champions League; each receipt has a UTC time.
3. Fetch **14 prior calendar days** of public completed scores for leagues with upcoming games, with a **35-day NFL/NCAAF** lookback,
   with source URLs and retrieval times. The capped maximum is **112 standard-league + 70 football** prior-score requests when all eight leagues are active, plus eight schedule requests. No inactive-league history requests are needed. All failures appear in the coverage report.
4. For a **future** game, construct at most five previous-game outcomes for
   each team, requiring three prior games and excluding results from
   games started less than 48 hours before the upcoming event.
   These are newly captured prospective features, **not proven historical
   as-of observations for older seasons**. A team with insufficient history
   has null form, not an invented zero or prior.
5. Match odds only where league, **full home and away team names**, and
   start time within ten minutes identify exactly one scheduled game.
   Reject future-dated, after-start, or stale quote receipts, and refuse
   to infer any player availability from NBA injury PDF or MLB rosters.
   Missing player-ID crosswalks and unconfirmed active lists remain blocked.
6. Save `prospective_event_evidence.jsonl`, `prospective_report.json`,
   `espn_schedule_capture.json`, `historical_published_results.jsonl`,
   and `historical_score_capture.json` as a **90-day research artifact**.

## What it does NOT do

- Archived SharpAPI and SportsGameOdds quotes are two aggregator observations,
  **not live independently verified DraftKings checkout prices**.
- An official PDF downloaded before tipoff is source inventory evidence, not
  confirmed healthy/active status for a specific player.
- Team form calculated prospectively is **not** historical verification that
  those same features existed at tipoff on games played months earlier.
- No input becomes `historical_results.jsonl`; no feature, outcome or quote
  is authorized for training by this stage.
- `Champion-001` remains untouched. Model probabilities, certified picks,
  qualified training records, EV rankings, and automated wagers remain zero.
- MLS and Champions League **three-way markets** are not converted to binary
  moneylines. Props require independent player identity/status and settlement
  support.

### Local run

```bash
python -m unittest discover -s tests -v
python challenger_prospective_pregame.py --history-days 14 --output-dir prospective_pregame
```

Optional `--sharp-jsonl`, `--sgo-jsonl`, and `--official-report` paths
reference **existing saved artifacts**. No credentials are needed.

**Next milestone:** retain recurring point-in-time source evidence across enough
games and seasons, independently adjudicate outcomes after settlement, and run
leakage-free walk-forward out-of-sample backtests and calibration. The frozen
Champion-001 may not be replaced without demonstrated improvement.

**Retention and cadence limitation:** GitHub Actions artifacts expire after 90 days,
so this is prospective evidence collection over a rolling window, **not yet a
multi-season permanent training archive**. Scheduled runs can be delayed, and
late quotes or events already in progress are rejected. A separately secured,
durable historical data store will be needed for multi-season research.

### Rolling evaluation window (October 29 update)

The outcome-linkage workflow reads up to the **latest 90 successful prospective
capture runs** (previously 14). With two captures per day, this is approximately
45 days of archives in the steady state, not 90 days of guaranteed coverage.
It reports the number of valid, unavailable/incomplete, and pre-baseline
archives in the GitHub Actions job summary. Missing runs, canceled schedules,
expired artifacts and missing results remain missing, never reconstructed.
This larger window raises download volume, and the Actions job has a 25-minute
limit. Artifact retention remains **90 days**; it is not an indefinite archive.

This stage only generates untrained $0 research forecasts. NFL and college
football may still have insufficient games in the extended lookback, especially
early in a season. Prospective snapshots and ESPN-published final links alone
do not establish qualified historical training rows, independent results
adjudication, calibrated forecasts, or expected value.
