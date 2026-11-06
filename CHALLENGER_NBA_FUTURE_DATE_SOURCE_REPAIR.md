# Challenger-001 — November 6 NBA future-date source repair

## Observed blocker
The November 6 early-morning eight-sport GitHub preflight (run 42156928560)
archived genuine research events and completed its safety sequence but logged an
NBA-owned season schedule HTTPError. The previous code attempted the NBA liveData
daily and NBA Stats ScoreboardV3 back-ups **only if at least one archived future
game was scheduled on the current Eastern date**. At night, today's games may
already have started while tomorrow's games still need a future pregame ID
crosscheck; in that case, only the CDN full-season schedule was attempted.

## Repair
- First request the NBA-owned full-season schedule once. If a valid future
  schedule is returned, use it, as before.
- Otherwise, attempt the NBA liveData daily scoreboard **only when the real
  observation day has upcoming archived NBA games**, then the NBA-operated Stats
  ScoreboardV3 **for each distinct archived future NBA Eastern game date**, at
  most seven days ahead. The date list is derived from archived ESPN pregame
  evidence, not an arbitrary endpoint or guessed game ID.
- Validate original NBA bytes, canonical Stats URL/date/league, exact
  scheduled status and tip time, ten-digit game ID, both canonical NBA team IDs,
  source receipt clock and strict ESPN same-matchup/60-second start agreement.
  A future-date Stats scoreboard is marked
  `nba_stats_scoreboard_v3_future_date` and is only game **identity** evidence.
  Existing same-day NBA active/inactive-status receipt checks are not relaxed.
- Capture real HTTP_403 vs HTTP_429 failure codes without response bodies,
  retries, secret output or access restriction workarounds.
- Continue through each expected future date; an unrelated date's successful
  scoreboard cannot suppress other dates' research.
- Preserve exact original source response bytes and SHA in the existing
  temporary GitHub research artifact. All model, prop, calibration and wagering
  certification remains blocked without independent supporting evidence.

## Verification
Offline fixture tests prove next-day fallback is attempted when the season
feed denies access, validate accepted original-source SHA and NBA game IDs, and
reject wrong dates, league IDs, stale days, >7-day requests and HTTP 429.
Existing NBA season/daily/Stats safety tests and the eight-sport preflight
workflow regression suite are also included.

This is an **access-path fix**, not proof that the NBA will allow GitHub-hosted
HTTP requests. If all three NBA-operated sources deny access, statuses remain
explicitly blocked and no official NBA game is fabricated. SportsDataIO is a
distinct third-party source with currently unverified numerical data entitlement;
it is not substituted for a league-owned receipt. Champion-001 is untouched,
Challenger-001 remains research-only, and no certified picks/wagers are created.
