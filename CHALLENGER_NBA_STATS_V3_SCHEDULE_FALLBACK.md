# Challenger-001: NBA Stats ScoreboardV3 — third pregame schedule fallback

## Live blocker

November 5, 2026 GitHub production audits showed HTTP 403 from BOTH NBA-operated CDN schedule sources:

- https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json
- https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json

Zero approved game IDs did not mean players were healthy, active, inactive or eligible for props. This development adds a third NBA-operated schedule route:

    https://stats.nba.com/stats/scoreboardv3?GameDate=YYYY-MM-DD&LeagueID=00

nba_api confirms this is the game-on-date NBA Stats endpoint: https://github.com/swar/nba_api/blob/master/docs/nba_api/stats/endpoint_guide.md

SportsDataIO is separately documented here: https://sportsdata.io/developers/api-documentation/nba. It is a **third-party source**, not NBA-operated and not an authenticated historical original NBA Active List. This change does not assume the user's SportsDataIO key is present or granted permission.

## Controls

- Source order is full NBA CDN season schedule, NBA CDN today's scoreboard, NBA Stats ScoreboardV3 for the **actual Eastern calendar day of the request**. Maximum one bounded fetch per source. HTTP 403, 429, timeout or malformed response is reported, not silently substituted with invented NBA game IDs.
- Stats ScoreboardV3 URL must be an exact NBA-operated URL with YYYY-MM-DD from actual observation time in America/New_York, no arbitrary requested date. Response requires leagueId 00, the same Eastern gameDate, valid distinct team names/team IDs, unique 10-digit game IDs, and valid scheduled future tipoffs. Started/final games cannot serve as prospective schedule inputs.
- The original bytes, SHA-256, source URL/kind, actual observation time and failures are saved together in the existing temporary source archive. File nba_official_schedule.json is a historical archive SLOT, not a claim that every archived source is the league's full season schedule.
- Prospective ESPN games must retain exact home/away clubs and start within 60 seconds of the NBA-operated game. Scheduled game-roster individual IDs remain exact-person/team/game NAME candidates, never certified final active list, independently authenticated ESPN/DraftKings ID mappings, or prop inputs.
- The subsequent NBA Stats BoxScoreSummaryV3 inactive stage accepts the new source kind only after independently rechecking the original SHA, canonical NBA Stats URL, actual original observed timestamp, Eastern same-day status and receipt age under ten minutes. On no Stats inactive list or a denial, all player states remain UNKNOWN; an unlisted player is never auto-active.
- ScoreboardV3 and BoxScoreSummaryV3 are both NBA-owned; using both is NOT independent third-party verification. Same-run hashes do not certify the original publication timestamp.

## GitHub Actions and offline testing

Both NBA original injury source and all-eight-sport prospective evidence workflows run the full offline safety suite for changes to the new source and its regressions; only main captures actual external source responses.

    python -m unittest discover -s tests -p 'test_challenger_nba_stats_v3_schedule_fallback.py' -v

All certified Champion-001 and Challenger-001 picks, independently qualified player-prop training observations, betting EV and wagers remain at ZERO. Champion-001 is untouched.

## Next priority

Check the FIRST post-merge production log for actual NBA Stats ScoreboardV3 acceptance. If its access is denied too, determine whether an authorized SportsDataIO NBA game schedule feed is connected, and use it strictly as a separately attributed provider crosswalk with original pregame as-of clocks. No third-party schedule can silently become NBA-operated evidence.
