# Challenger-001: NBA-operated Stats V3 explicit pregame inactives — research only

## Critical distinction

The NBA official Active List governs eligibility (NBA Bylaws Article 6.02). Injury reports and a scheduled NBA liveData player status field are NOT independently authenticated complete game Active Lists, nor bookmaker settlements.

The separate NBA-operated Stats BoxScoreSummaryV3 endpoint contains homeTeam.inactives and awayTeam.inactives with personId, firstName, familyName. This adds explicit game-level inactive claims as observed, but accessibility/availability before tipoff has not been independently established. It can deny GitHub-hosted clients (HTTP 403) or return only after a game; any such restriction remains an **unavailable source**, not certified active/inactive status. No WAF bypass.

Published API schema: https://nba-api-ts.riccardo.lol/endpoints/stats/box-scores/box-score-summary-v3/
Endpoint template: https://stats.nba.com/stats/boxscoresummaryv3?GameID={10-digit-game-id}

## Implemented safeguards

- Only read original NBA-operated full season schedule JSON and SHA-256 receipt saved by the existing pregame roster-ID source capture. No previously captured schedule means ZERO Stats V3 calls. Altered source bytes block the stage.
- Select at most four scheduled games, starting within two hours of actual request time. Never backdate a postgame response as pregame evidence.
- Single bounded request per game, maximum 4 MB, 15-second timeout. Only approved exact NBA Stats game URL, no sportsbook or paid odds provider.
- Require the response to finish BEFORE tipoff. Require gameStatus scheduled (1), exact official NBA game ID, source home/away NBA team IDs match the original NBA season schedule, exact official club names and tricodes, and start time within 60 seconds of original source.
- Require explicit inactives array on both clubs, even if empty. Missing arrays, duplicate person IDs, unexpected player names, wrong clubs, game start mismatch, post-tipoff status or access denial all block the source; no imputation.
- Record only explicit NBA personIds of players listed inactive by the NBA Stats response. **Never infer that an omitted player is active.** An empty list is not evidence of a complete Active List, and listed names are not accepted as final official eligibility or a prop void.
- Save every accepted original response's exact bytes and SHA-256 in the same research artifact. Actual observation time is recorded; original NBA publication timestamp is not authenticated.
- All outputs preserve FALSE player-prop training, model probability, certified prediction, active/inactive certification, bookmaker settlement and bet-ready flags.

## Continuous integration

The existing standalone NBA official injury source workflow and all-sports prospective evidence workflow call challenger_nba_official_stats_v3_inactives.py after their NBA original pregame schedule / roster archive. They report zero correctly when no games are within the 120-minute window or the NBA source is unavailable. No retrospective data can substitute for as-observed pregame evidence.

Artifacts under stats_v3_inactive_receipts:
- nba_stats_v3_inactive_report.json
- nba_stats_v3_inactive_review.jsonl
- nba_stats_v3_original_source_bytes/{gameId}.json, only for actually retrieved and validated scheduled-game response

Usage after an original schedule capture:

    python challenger_nba_official_stats_v3_inactives.py --roster-dir nba_injury_current_original/pregame_roster_id_review --output-dir nba_injury_current_original/stats_v3_inactive_receipts

Offline regressions:

    python -m unittest discover -s tests -p 'test_challenger_nba_official_stats_v3_inactives.py' -v

## Remaining blockers

- A separately authenticated complete game-specific NBA official Active List source observed pre-tipoff with unambiguous publication/eligibility meaning and original timestamp.
- Actual NBA/ESPN/DraftKings player-ID crosswalk, pregame projected minutes and role/usage, bookmaker-specific late-scratch and settlement rules, and independently validated, calibrated model probabilities/EV.
- A genuine historical pregame feature archive and minimum independent chronological training/holdout coverage.

**Champion-001 remains frozen. This change certifies ZERO player props, ZERO positive-EV bets, ZERO active/inactive lists, ZERO eligible training games and ZERO wagers.**
