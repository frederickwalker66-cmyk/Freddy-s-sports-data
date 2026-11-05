# Challenger-001: NBA public CDN request compatibility and exact HTTP failure diagnostics

## Evidence from the prior live fallback

The November 5, 2026 GitHub Actions run 42058673852 showed that BOTH NBA-operated source requests failed at HTTP retrieval:
- https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json
- https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json

The existing model recorded only the Python class HTTPError for each source, so an access denial, expired endpoint, or rate limit could not be distinguished by report. The Stats V3 inactive source appropriately made zero requests because no authenticated game schedule had been obtained. **Zero was missing data, not evidence all players were active.**

## Fix

The NBA schedule and scheduled-state game-roster fetcher now uses ordinary browser-compatible public CDN HTTP content negotiation, matching the request profile used by the existing NBA schedule clock module and maintained public NBA data clients: a standard Chrome user-agent string, JSON/text accept header, language, NBA.com Origin and Referer. No proxy rotation, WAF challenge solving, IP masking, login, access token tricks, extra retries or unauthorized source is used.

The collector still attempts only the two explicitly whitelisted NBA-operated schedule resources (season first, same-day scoreboard second). Its error report now records a safe numeric status such as HTTP_403 or HTTP_429 rather than collapsing all denials to HTTPError. Raw response bodies/credentials are never logged. On HTTP errors, no fetched bytes, NBA game IDs, active/inactive player data or odds are invented.

## Regression coverage

New tests ensure:
- Both approved NBA-operated schedule source URLs use the same standard headers and exact timeouts, preserving response bytes.
- Unknown URLs and wrong byte budgets are blocked before any network call.
- Two HTTP 403 failures are explicitly reported as HTTP_403 for each source, with no qualified identity or trained player prop.
- HTTP 429 responses are labeled separately and never retried in an uncontrolled loop.

The existing same-day scoreboard fallback still rejects stale/future/wrong-league boards and enforces original source bytes, source URL/kind, team IDs, exact game IDs, NBA/ESPN game times and same-day receipt freshness downstream.

## Remaining caveat

NBA-operated public CDN responses can still be denied from a GitHub runner despite valid normal headers. A successful code deployment does not prove that access was restored. Real source success must be demonstrated by a new GitHub Actions report showing verified schedule source kind, original bytes SHA and actual eligible scheduled NBA game IDs. Then NBA Stats V3 inactive evidence can be evaluated only within the two-hour pregame window, without ever declaring the full official Active List authenticated.

Champion-001 remains frozen. Zero certified player prop forecasts, independently qualified training records, verified positive-EV bets or automated wagers from this change.
