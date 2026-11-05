# Challenger-001 Upgrade #78 — NBA-operated original-source game ID crosscheck

## Scope

Continue #76 (NHL) and #77 (MLB) with a **third independently operated
schedule feed**, using only NBA league-operated public JSON resources. The
source is independent of ESPN's schedule observation, not independent odds,
player eligibility, model probabilities, or publisher-signed historical
timestamp authentication.

## Sources and conditional failover

Only when a future NBA event was archived in the verified ESPN preflight:

1. NBA season schedule at
   `https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json`
   can cover games over the seven-day outlook.
2. If the season source is unavailable, and the NBA archived a game for the
   **current Eastern day**, use NBA-operated daily scoreboard:
   `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`.
3. If both are unavailable, attempt the canonical date-specific NBA Stats
   ScoreboardV3 `GameDate=<actual ET date>&LeagueID=00` resource.

No fallback is permitted to verify a future day's game from today's board.
No proxy/CAPTCHA bypass, backdated observations, or synthetic source evidence.
Genuine blocked responses (including HTTP 403) remain evidence of **failure**.

## Strict identity acceptance

- Original NBA HTTP bytes, observed UTC, exact source URL and local SHA-256.
- Official NBA league identity `00`, ten-digit official `gameId`,
  the published game start instant and explicit home/away orientation.
- Canonical full NBA team names and separately checked NBA numeric team IDs
  against the fixed NBA team registry. Clippers have a narrowly defined
  LA/Los Angeles full-name alias; no nickname or fuzzy guessing.
- ESPN archive completed before actual official NBA source receipt, and both
  precede the first scheduled tipoff.
- Exactly **one** matching official NBA game with kickoff differing from the
  original ESPN start by at most 60 seconds.
- No reused official game ID for multiple ESPN archived games, no
  conflicting official revisions, no in-progress/finished promotion.

Failed/late/malformed official sources, conflicting starts, identity
ambiguity, and unsupported names are explicitly quarantined.

## Files and artifact

- `challenger_nba_official_pregame_schedule.py`
- `challenger_eight_sport_independent_identity.py`
- `tests/test_challenger_nba_official_pregame_schedule.py`
- `.github/workflows/challenger-eight-sport-source-preflight.yml`

The one-time main-branch preflight stores original NBA response bytes (one of
`nba_official_season_schedule.json`,
`nba_official_today_scoreboard.json`,
`nba_official_stats_v3_scoreboard.json`), and includes per-game NBA IDs,
official team IDs, source hashes, observations and reasons in the existing
`independent_identity/` report. Its ongoing scheduled collectors are unchanged.

## Verification

```bash
python -m unittest discover -s tests -p 'test_challenger_nba_official_pregame_schedule.py' -v
python -m unittest discover -s tests -p 'test_challenger_eight_sport_independent_identity.py' -v
python -m unittest discover -s tests -p 'test_challenger_mlb_official_pregame_schedule.py' -v
```

A synthetic successful game crosswalk is **not** a real-world live match
count. Inspect real post-merge GitHub artifacts for live coverage. A locally
computed original-response hash is not a publisher-signed timestamp.

## Certification safeguards

- Frozen Champion-001 unchanged.
- No independently verifiable model probabilities or certified selections.
- No direct DraftKings market ID, exact main-line selection, price or checkout
  timestamp independently verified.
- No promoted historical training games, certified EV or wagers.
- NFL, NCAAF, NCAAB, MLS and UEFA Champions League remain unverified pending
  separately built league-operated source adapters.

**Next (#79):** A dedicated audited, directly observed sportsbook
event/market/selection/line/price receipt schema before any value ranking;
never substitute market no-vig probabilities for a native model output.
