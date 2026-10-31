# Challenger-001 multi-season historical result database (research only)

This creates an indexed, downloadable SQLite database from **actual GitHub Actions
historical-score archives**. It does not generate, invent, interpolate or assume
scores for dates not present in archived sources.

## What is implemented

- `challenger_multiseason_history.py` scans previously collected
  `challenger-backfill-LEAGUE-RUN_ID` archives for eight leagues, checks their
  original source coverage reports, result identity, original ESPN scoreboard
  query date, season type, and fail-closed research-only safety flags.
- Calendar-year season IDs for MLB/MLS and cross-year IDs (such as
  `2025-26`) for NBA/NFL/NHL/NCAAF/NCAAB/UEFA Champions League.
- SQLite `archive_windows`, `published_games`, `source_observations`
  and `conflicting_events` tables. `published_games` is indexed on
  league/season/date and team IDs.
- A repeated event across two archival runs is counted **once** if the
  event, both teams, kickoff, score and season type agree; distinct raw
  retrievals are recorded as separate provenance observations. Conflicting
  results are quarantined for review and excluded from the game table.
- Coverage report `history_coverage.json` shows per-league-season recorded
  games, fetched source days, accepted/rejected windows, and conflicts.
  A fully fetched source window is NOT a complete sports season.
- The existing historical-backfill Actions workflow now downloads its
  own eight finished league archives plus up to six previously successful
  batches, consolidates them, validates the safety flags and saves the
  SQLite and coverage report under `challenger-multiseason-research-RUN_ID`.
  Collection remains capped to 35 days per league and the consolidator
  makes zero additional ESPN or sportsbook API calls.

## Download and use

From the latest successful
`Challenger-001 capped eight-league historical results (research only)`
workflow run, download artifact `challenger-multiseason-research-RUN_ID`.
It includes `historical_published_scores.sqlite` and
`history_coverage.json`.

Example read-only queries:

```sql
SELECT league, season, COUNT(*) AS games
FROM published_games
GROUP BY league, season
ORDER BY league, season;

SELECT event_date_et, home_team, away_team, home_score, away_score
FROM published_games
WHERE league='nba' AND season='2025-26'
ORDER BY event_date_et;
```

## Trust boundaries

The database contains **ESPN-published results observed retrospectively**.
It does not contain historical player box scores, player props, direct
DraftKings prices, reconstructed as-of rosters, official league adjudication,
independent cryptographic timestamps or qualifying model training labels.
Retrospective score ingestion CANNOT be used as a substitute for a true
pregame prediction ledger. Soccer knockout 90-minute versus extra-time market
settlement is unverified. Source file hashes identify archive bytes but do
not independently authenticate origin or original publication date.

**Storage warning:** GitHub Actions artifacts expire after **90 days** for
this SQLite output, and older source backfill archives expire after 30 days.
Thus this is **not yet a durable multi-decade history store**. Before those
dates, copy the research archive to a user-approved durable bucket or database
with immutable versioned storage; that destination has not been connected or
configured. Do not claim 1950–2026 completeness: source existence, league
founding dates and historical per-season completeness remain unverified.

Next development milestone: independently sourced per-player historical
box scores for eight leagues, including minutes/snaps/TOI/innings and
per-market settlement schema; validate event/player identities and retention
before any player-prop model. Do not fabricate unavailable stats.

## SportsGameOdds opt-out

Historical and prospective production workflows do not call SportsGameOdds
or reuse archived SportsGameOdds observations. SharpAPI remains available
for supported current *research-only* markets. The historical database uses
no paid odds provider.

Original Champion-001 remains frozen. Challenger-001 is research-only.
There are zero qualified training examples, independently certified
predictions, automated wagers or bet-ready selections.
