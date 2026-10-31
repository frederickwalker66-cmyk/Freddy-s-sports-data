# Freddy's Picks AI — Eight-sport historical game-result archive

Status: **research-only**. No SportsGameOdds. No trained model or betting.

## Supported competition feeds
| Competition | Historical public source | Result type and trust boundary |
| --- | --- | --- |
| NBA | ESPN basketball/nba | Published final home/away; regular season only; independently adjudicated result NOT established |
| NFL | ESPN football/nfl | Published final home/away; overtime/tie market settlement NOT verified |
| MLB | ESPN baseball/mlb | Published final home/away; suspended/shortened/extra inning settlement NOT verified |
| NHL | ESPN hockey/nhl | Published final home/away; 60-minute versus OT/shootout market rules NOT verified |
| NCAAF | ESPN football/college-football | Published final home/away; college eligibility and bookmaker settlement NOT verified |
| NCAAB | ESPN basketball/mens-college-basketball | Published final home/away; college settlement NOT verified |
| MLS | ESPN soccer/usa.1 | Published full-game score; standard 90-minute home/draw/away NOT verified |
| UEFA Champions League | ESPN soccer/uefa.champions | Published full-game score; extra time/penalties versus 90-minute home/draw/away NOT verified |

## Historical coverage, not invented seasons

The collector supports **bounded historical windows with start dates from January 1,
1950 onward through the most recent completed day**, but ESPN's actual
archive and competition histories differ. **This does not mean there are complete
scores from 1950 for every league**. Some competitions did not yet exist,
and ESPN may return no events or failed days. The output records missing days
and never creates games, scores, odds or player props to fill gaps.

Each invocation requests **at most 35 calendar days of one league** (one ESPN
scoreboard call per day). The eight-league GitHub workflow runs separate,
two-at-a-time jobs, so maximum public scoreboard requests is 280 per full
35-day eight-league batch. There are zero sportsbook or SportsGameOdds API
requests. Multiple seasons require separately selected windows and audited
coverage before any full-history claim; archives may expire from GitHub Actions
after 30 days unless migrated to durable storage.

## GitHub Actions

`.github/workflows/challenger-historical-backfill.yml`
runs eight historical league backfills on `main` changes or manual dispatch.
For manual dispatch choose an **optional end date** (`YYYY-MM-DD`, same
date for all eight leagues) and **days** (`1`–`35`); omitted end dates
use in-season defaults for each league.

Per league, artifacts contain:
- `published_results.jsonl`: public final scores, times, team IDs, league,
  recorded result (home/away/draw) and source URL, NOT verified settlement.
- `backfill_coverage.json`: source successes/failures, home/away/draw counts,
  selected window, completion flag and unverified market category.
- `scoreboard_collection.json`: source-day request coverage.
- `research_candidates.jsonl`: only **nontrainable** retrospective
  *binary* research features for leagues where enough team history exists.
  Soccer leagues produce **no binary moneyline candidates**.
- `candidate_coverage.json` and `walkforward_diagnostic.json`:
  retrospective research and exploratory diagnostics, NOT measured model
  performance on independently verified historical point-in-time features.

Example individual window:
```bash
python challenger_historical_backfill.py --league mls --days 35 \
  --end-date 2026-08-15 --output-dir challenger_backfill
python challenger_historical_backfill.py --league uefa_champions_league --days 35 \
  --end-date 2026-03-18 --output-dir challenger_backfill_ucl
```

## How to reach a real multi-decade archive

1. Partition by league, season and bounded date window; store immutable
   source receipts with day/season completeness reports and true retrieval
   times; never overwrite older snapshots silently.
2. Reconcile exact event and team identities to an independent league
   operated or trusted secondary provider, including time and final-score
   conflicts, postponed/cancelled games and sport-specific market settlement.
3. Keep final-score archives separate from true *pregame-as-of* roster, usage,
   schedule strength and other features. Retrospective features do not prove
   publication before the original event.
4. Fit **separate** sport/market models only on independently audited,
   time-ordered evidence, with held-out later games and prospective shadows.
   Player-prop histories require independently sourced player box scores
   and minutes/snaps/TOI/innings, not merely final team scores.

Never use this archive as `historical_results.jsonl` or automatically
set `qualified_for_challenger_backtest` to true. Champion-001 remains
unchanged. No certified forecasts, no bets, no implied profitability.
