# Challenger-001: NBA two-source postgame player statistics review

## Purpose

Develop player-prop historical outcome integrity without conflating postgame stats with pregame predictive features. The pipeline first requires existing ESPN versus NBA-owned **final game score agreement**, then checks each player's ESPN postgame box score against the NBA-owned public postgame box score. Research only.

- ESPN single-game source: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={espn_event_id}
- NBA league-owned source: https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{nba_game_id}.json
- Up to three unique previously corroborated NBA games per run and two requests per game, 4MB bounded reads. No sportsbook or paid odds calls.
- Require exact ESPN event ID ↔ league-owned 10-digit game ID from the existing official scoreboard crosscheck, game final status, same home and away team names, exact team scores, correct ESPN team IDs and nonambiguous player identities.
- Match players by normalized exact name *within the already-matched team*, retaining both separate original player IDs. Unknown names remain unmatched; duplicates and mixed teams fail closed.
- Compare postgame full-game points, total rebounds, assists, steals and blocks for actual participants. A DNP confirmed by both sources is reported separately, **not** converted into a zero-point under or an automatic void. Contradictions remain blocked. Missing stats are never imputed.
- Retain unmodified response bytes plus SHA-256 from each source in the existing temporary GitHub Actions artifact.
- Any missing or denied official source remains a research blocker, not a negative performance outcome.
- The original ESPN and NBA publisher agreement is *independent source corroboration*, not original publication-time authentication and not a sportsbook settlement receipt.

## Outputs and workflow

The existing GitHub Actions workflow challenger-prospective-outcome-validation.yml adds a player-review stage **after** NBA league-owned final-score corroboration.

It writes:
- prospective_validation/nba_player_two_source_review.jsonl
- prospective_validation/nba_player_two_source_report.json
- prospective_validation/nba_player_original_source_bytes/{ESPN_ID}_espn.json (on valid two-source fetch)
- prospective_validation/nba_player_original_source_bytes/{ESPN_ID}_nba.json (on valid two-source fetch)

Manually invoke:

    python challenger_nba_player_two_source_review.py --official-crosschecks prospective_validation/nba_official_final_crosscheck.jsonl --output-dir prospective_validation --max-games 3

    python -m unittest discover -s tests -p 'test_challenger_nba_player_two_source_review.py' -v

## Next evidence requirements

1. Authenticated timestamped **pregame** injury and roster availability, minutes/usage role changes and late scratch decisions.
2. An independent NBA person ID, ESPN athlete ID and DraftKings player identity crosswalk (same-looking names are insufficient).
3. Exact bookmaker player prop type, threshold, quote time and late scratch, push, OT and DNP settlement rules.
4. Independent chronological model training and holdout data, actual *pregame* model probabilities and calibration; no manufactured scores, bets or forecasts.
5. Extend to NFL/NHL/MLB/college player-prop sources with league-specific rules, never import NBA scoring assumptions into different sports.

No certified Champion-001 or Challenger-001 picks, independently qualified training observations, trained player-prop models, verified positive EV, or automated wagering results arise from this module. Champion-001 remains frozen.
