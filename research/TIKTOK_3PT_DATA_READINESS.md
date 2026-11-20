# NBA 3PT research — actual-data readiness and offline execution

This is Challenger research only. No Champion-001 changes, bets, or certified predictions.

## Confirmed existing source
`challenger_nba_player_boxes.py` can collect bounded ESPN final NBA player
box scores (including `threes_made`, `minutes`, `event_start_utc`,
`player_id`, `event_id`). It requires a pre-existing SQLite history database
with a `published_games` table. Its rows explicitly indicate that player
statistics are **not independently verified**.

## What the repository does NOT currently supply
The repository tree inspection on 2026-11-20 found no tracked `.csv`,
`.jsonl`, `.db`, or `.sqlite` historical dataset. Thus no actual
player-game sample size, hit rate, ROI, or 90% result can be reported from
committed repository data. GitHub Actions artifacts or other external
storage might contain relevant data; these have not been authenticated here.

The existing box-score collector also does **not** provide historical
pregame opponent 3PM-allowed rank, pregame shooter rank, DFS ownership,
timestamped sportsbook prop lines, or independently certified model
probabilities. Do not substitute final-game or current-day rankings for
pregame rankings.

## Reproducible offline pipeline once actual data is available

1. Collect ESPN research rows from a properly configured archived history DB:
   `python challenger_nba_player_boxes.py --history-db PATH_TO_HISTORY.db --limit 5 --output-dir player_boxscore_research`
2. Produce strictly earlier-game player 3PM rolling features:
   `python -m research.tiktok_nba_boxscore_adapter --boxes player_boxscore_research/nba_player_boxes_research.jsonl --output player_boxscore_research/three_point_features.json`
3. Review the report. This step does not provide an independently qualified
   pregame betting backtest, because verified pregame rankings, odds, and
   provenance are missing.
4. For a separately authenticated point-in-time pregame CSV, run:
   `python -m research.tiktok_three_point_backtest --input VERIFIED_PREGAME_ROWS.csv --output three_point_backtest.json`
5. Independently reconcile final player stats, sportsbook settlement rules,
   line timestamps, pregame feature availability, and model calibration
   before any positive-EV or TAKE certification.

### Mandatory reporting
Report actual sample size, eligible sample size, wins/losses, confidence
intervals, pricing/ROI where defensible, and all quarantines. No fabricated
historical records or unverified 90% claims. Keep all box-score-adapter
outputs HOLD / UNCERTIFIED_RESEARCH_ONLY.
