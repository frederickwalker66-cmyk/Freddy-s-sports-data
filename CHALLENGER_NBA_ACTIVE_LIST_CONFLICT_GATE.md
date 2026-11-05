# Challenger-001 — NBA game-day preliminary active/inactive conflict gate

**This module does NOT certify a player's final official NBA Active List membership. It is a fail-closed prerequisite for eventually obtaining reliable NBA player-prop availability inputs.**

## Critical source distinction

Under NBA bylaws, the official **Active List** controls which players may dress and be eligible for each game. The NBA injury report uses designations such as Out, Questionable, Probable and Available and is updated during the day, but is **not the complete official game Active List**. Similarly, the public NBA liveData game boxscore can contain a per-player string such as ACTIVE or INACTIVE while still in scheduled state; that field cannot by itself establish the final official Active List or DraftKings settlement.

References: official NBA bylaws Article 6.02 (Active List) at https://cms.nba.com/wp-content/uploads/sites/4/2024/06/NBA-Consitution-By-Laws-June-2024.pdf ; official injury reporting https://official.nba.com/nba-injury-report-2026-27-season/ ; NBA-owned liveData boxscore https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json.

## Implemented

The new module challenger_nba_active_list_conflict_gate.py consumes **only actual archived bytes produced by the earlier original NBA injury PDF + scheduled NBA game-roster collector**, not newly reconstructed historical pregame records or any sportsbook data.

1. Require the prior player-ID candidate research report and rows to maintain all zero-certification flags. Recheck every original source SHA-256 receipt (season schedule and individual scheduled-state boxscores). Missing, altered, noncanonical source files block the comparison.
2. Require the same NBA game ID, matching exact home/away clubs, verified game date in Eastern time, same schedule-vs-boxscore tipoff (within 60 seconds), scheduled game status **1**, and actual roster observation strictly earlier than tipoff. Never use live/final scores as pregame data.
3. Cross-check the already-unqualified NBA person ID candidate, correct team ID, exact normalized player name, and raw roster status and not-playing reason against the original saved NBA game source. Reject or block identity drift.
4. Distinguish early roster snapshots (more than 90 minutes before tipoff), injury reports older than three hours at roster observation, missing/ambiguous player IDs, and unknown raw roster status instead of guessing eligibility.
5. When both sources were actually observed before tipoff and satisfy the time bounds, flag **Out in injury PDF vs ACTIVE in preliminary game roster** or **Available in injury PDF vs INACTIVE in preliminary game roster** as *manual review conflicts*, not as player availability certification.
6. Even "Out + INACTIVE" agreement means **research-only preliminary corroboration**, not a confirmed final active/inactive roster, wager void, DNP, under bet or demonstrated player-prop model edge.
7. The checks are integrated in the NBA injury-source workflow and the all-eight-sport prospective workflow. Results are archived with the same temporary GitHub Actions artifacts.

Outputs: nba_active_list_conflict_review.jsonl and nba_active_list_conflict_report.json.

Manual invocation after the original identity-candidate stage:

    python challenger_nba_active_list_conflict_gate.py --roster-dir nba_injury_current_original/pregame_roster_id_review --output-dir nba_injury_current_original/active_list_conflicts

## What would be necessary for true active/inactive verification?

- A separate **game-specific complete Active List** or an independently authenticated league/official scorer source with its actual as-of observation time, precise game and NBA person IDs and an enforceable publication/eligibility definition. The existing scheduled-state boxscore's status field is not sufficient to set the certified active flag.
- Independent NBA-personId ↔ ESPN-athleteId ↔ DraftKings-playerId crosswalk and verified late scratch effects.
- Actual bookmaker market, quoted timestamp, void/settlement and overtime rules; independently timestamped projected minutes/usage and true prospective holdout probability calibration.
- Continuous storage across capture runs with authenticated publication provenance, not merely report filename times or same-run GitHub-generated hashes.

**Certification counters remain zero by design. Champion-001 remains completely frozen.**
