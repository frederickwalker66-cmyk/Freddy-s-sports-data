# Challenger-001 — NBA league-operated daily scoreboard fallback for pregame IDs

## Why this development step exists

The NBA person-ID injury and NBA Stats V3 inactive sources previously required the NBA-operated full season schedule at https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json. A hosted GitHub runner could fail to retrieve that source, leaving zero verified event identity and zero NBA Stats V3 attempts.

The same NBA owns a smaller, public **today's scoreboard** at https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json. Its structure is documented in the maintained nba_api live scoreboard guide:
https://github.com/swar/nba_api/blob/master/docs/nba_api/live/endpoints/scoreboard.md

This upgrade attempts the daily scoreboard ONLY after a missing/invalid season schedule. Both are original NBA-operated source data, not an independent cross-provider schedule agreement. A working fallback is NOT a verified full game-day Active List, pregame player activity proof or betting eligibility certificate.

## Source controls

- The existing pregame roster collector first requests the official NBA full season schedule. If that request fails or returns an invalid season-schema document, it makes one bounded request to the exact NBA liveData daily scoreboard URL. No arbitrary hosts, redirects to unofficial sources or paid odds sources are used.
- The new helper challenger_nba_daily_scoreboard_fallback.py requires original JSON bytes, a real time-zone-aware observation time, leagueId 00, a gameDate that equals **the actual Eastern calendar day of capture**, a maximum of 25 game records, unique ten-digit NBA game IDs, and valid distinct official team names/team IDs.
- The common NBA schedule parser must recognize every game marked scheduled, with the NBA-supplied game time and home/away clubs. Only games starting AFTER actual capture are future pregame events.
- A stale/yesterday daily board, next-day board, malformed JSON, ambiguous NBA game, missing team ID, duplicate game IDs, wrong league, unavailable CDN or invalid timestamps remain unavailable evidence. The helper does NOT guess games from an ESPN schedule or pre-existing NBA postgame records.
- Both original source variants are saved as **actual raw JSON response bytes** in the existing temporary prospective archive with SHA-256 and observation time. The source URL/kind and primary failure class are recorded in nba_pregame_roster_identity_report.json. The filename nba_official_schedule.json is a source *slot*: the embedded JSON kind and recorded URL explicitly indicate whether it contains the original season schedule or original same-day scoreboard.
- Game-specific NBA scheduled-state player roster fetching still requires exact NBA game ID, verified teams, tipoff time within 60 seconds, source download ending before kickoff, unique NBA person IDs, and no actual player-eligibility promotion.
- The downstream NBA Stats V3 inactive stage now accepts either source variant. When the source is the daily board, it **revalidates the original bytes, source kind, source URL, source SHA, original actual observation time, current Eastern date, and source age ≤10 minutes** before making any game-specific request. It still requests at most four official games starting in the next two hours and never treats a scheduled roster/status or absent name as verified active.
- ESPN ↔ NBA game reconciliation remains separately required if real prospective ESPN event snapshots are present; same-day NBA game identities alone do not authenticate sportsbook event/player mappings.
- A GitHub artifact receipt/hash does not independently establish the original NBA publication time or that the daily scoreboard/Stats V3 endpoints were actually reachable for all game dates.

## Integrated tests and artifacts

The standalone NBA injury report workflow runs 19 new synthetic fallback regressions and retains the same actual-time, source-byte and zero-certification assertions. The eight-sport prospective workflow also triggers on source or test changes and executes the full offline unit suite.

Research scripts:

    python challenger_nba_pregame_roster_identity.py --capture-dir nba_injury_current_original --output-dir nba_injury_current_original/pregame_roster_id_review
    python challenger_nba_official_stats_v3_inactives.py --roster-dir nba_injury_current_original/pregame_roster_id_review --output-dir nba_injury_current_original/stats_v3_inactive_receipts

Offline regression suite:

    python -m unittest discover -s tests -p 'test_challenger_nba_daily_scoreboard_fallback.py' -v

The original game source remains alongside each stage's pregame game-roster JSON bytes and original SHA receipts inside the temporary GitHub Actions artifact, never retrospectively recreated from a later result.

## Remaining work

1. Verify in actual live GitHub runs that the NBA daily scoreboard is accessible when the full season source fails, and that prospective NBA game match counts improve without a timing/identity mismatch.
2. Separately establish availability and pretipoff timing of NBA Stats V3 explicit inactives; a source denial or absent entry remains UNKNOWN.
3. Authenticate complete game-specific official NBA Active Lists, then independent NBA↔ESPN↔DraftKings player identity linkage and exact pregame projected minutes/usage, sportsbook void/settlement terms and chronological model calibration.

**This upgrade does not modify Champion-001 or certify any model forecasts, independently verified Active Lists, training examples, positive-EV player props, or wagers. All such counters remain zero.**
