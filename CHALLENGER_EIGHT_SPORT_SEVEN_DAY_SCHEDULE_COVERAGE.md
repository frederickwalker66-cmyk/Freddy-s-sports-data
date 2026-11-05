# Challenger-001 — Eight-Sport Seven-Day Pregame Schedule Coverage

## Problem addressed

Earlier source audits found zero receipt-backed archived games for NFL, MLB, NCAAB, and UEFA Champions League. The prospective collector previously requested only the current Eastern day. A league with no remaining game TODAY could appear empty even when the next fixture was scheduled days later. A zero count alone could not distinguish no ESPN listing, games already played, a denied source, malformed data, and missing archive records.

## Implementation

1. The public ESPN schedule adapter retains its original one-day behavior by default, with an opt-in 0–7 day lookahead. The live Challenger prospective workflow now enables seven days. It checks today first and, for each sport with zero eligible future games today, checks up to seven subsequent Eastern dates. It stops on the first date with eligible upcoming games rather than scanning all dates unnecessarily.
2. Eight leagues remain separate: NBA, NFL, MLB, NHL, NCAAF, NCAAB, MLS, UEFA Champions League. A scheduled fixture requires ESPN event ID, distinct home/away team names, parseable UTC tipoff, ESPN pregame state, and actual prospective observation time before tipoff. Duplicates and unsupported source data fail closed.
3. Bounded by eight ESPN scoreboard requests per league (today plus seven future dates; at most 64 across all eight). Each retrieved day records ESPN raw game-listing count, state counts, invalid/unusable entries, future eligible fixtures, source URL and explicit failure class. The collector never invents events on unqueried days.
4. In a separate read-only audit, the original schedule JSON, actual prospective event archive, and prospective summary are reconciled by exact league and original ESPN event ID. It verifies that discovered future games have a matching archived record, preserving strict no-model/no-bet flags and source clocks.
5. Distinguishes complete ESPN empty-listing windows, listings that are already started or unusable, partial/total retrieval failures, discovered-but-unarchived games, and successfully archived research schedules. These are classifications of ESPN observations, not authenticated official league no-game statements. Failed dates always prevent an authoritative no-games claim.
6. The existing 14/35-day lookback for published research results continues unchanged. An ESPN upcoming schedule is never an authenticated pregame model forecast, player-active clearance, verified DraftKings checkout quote or certified probability.
7. Writes prospective_pregame/eight_sport_schedule_coverage.json to the existing temporary 90-day GitHub Actions artifact. GitHub tests cover different fixture patterns, no-game dates, partial failures, NFL and UEFA future games, source duplicates, unsupported odds/Champion promotion, exact lineage and original timestamp constraints.

## Operational limits and next decisions

- A seven-day outlook can find the next NFL weekend or UEFA matchday, but a game on day eight is outside the checked window and cannot be called absent. ESPN can omit or change future fixtures; this is third-party research evidence.
- The previous NCAAF 47/47 and NHL 10/10 score agreements are retrospective score corroboration, NOT qualified pregame features or betting accuracy. Extending schedule coverage does not create trained models.
- After the first successful live lookahead audit, use per-league source diagnostics to prioritize true access failures, historical missing receipts, market-specific bookmaker void/settlement verification and independent source authentication.
- Champion-001 is completely frozen. The module writes zero qualified training records, zero certified Champion/Challenger picks, zero verified positive-EV bets and zero wagers.

Offline test command:

    python -m unittest discover -s tests -p 'test_challenger_eight_sport_schedule_outlook.py' -v

Live research-only report command:

    python challenger_all_sports_schedule_coverage.py --capture-dir prospective_pregame
