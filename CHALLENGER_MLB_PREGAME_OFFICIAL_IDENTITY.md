# Challenger-001 Upgrade #77 — MLB league-owned pregame identity

## Purpose

Extend #76's independent NHL game identity checks to the MLB-operated Stats
API without touching the frozen Champion-001 model or betting certification.
This is an **additional source corroboration**, not confirmation of
bookmaker market identity, line availability, odds or positive EV.

## New MLB evidence

For each archived prospective MLB event, the original MLB Stats API schedule
response is obtained from the exact canonical date endpoint:

`https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=YYYY-MM-DD`

The source and audit retain original response **bytes**, SHA-256, actual
observed UTC time, URL, official gamePk, both teams' numeric MLB IDs and full
names, game type, and exact first-pitch UTC. Strict checks require:

1. Valid original league-operated response for the relevant game date, captured
   after the ESPN pregame archive and strictly before first pitch.
2. Distinct official numeric home and away team IDs and exact full team-name
   agreement with archived ESPN names; no nickname-only or fuzzy matching.
3. A unique official `gamePk` with start within **60 seconds** of ESPN's
   archived UTC kickoff; no reused MLB ID for multiple ESPN games.
4. No contradictory official source revisions, swapped sides, malformed
   statuses, postseason/exhibition confusion or late source captures.
5. For 00:00-04:59 Eastern starts, the previous Eastern date is also checked
   because a stadium-local MLB official date may differ.

If MLB is outside its season and no future game was archived, the additional
fetcher makes **zero** MLB requests. An empty official schedule is accepted as
empty source evidence and cannot generate a betting pick.

## Outputs

The original preflight artifact additionally contains:
- `independent_identity/mlb_official_YYYYMMDD.json` original MLB responses
- `independent_identity/independent_game_identity.jsonl` with separate league
  identity findings and exact official MLB gamePk/teams
- `independent_identity/independent_game_identity_report.json` with
  `independently_observed_mlb_pregame_identity_matches_research_only` and
  `mlb_source_errors`.

The existing NHL game identity adapter remains in place. NBA, NFL, NCAAF,
NCAAB, MLS and UEFA Champions League are still marked
`official_league_adapter_not_available`.

## Synthetic safety tests

```bash
python -m unittest discover -s tests -p 'test_challenger_mlb_official_pregame_schedule.py' -v
python -m unittest discover -s tests -p 'test_challenger_eight_sport_independent_identity.py' -v
```

The suite asserts correct ID/side/time matching, no invented offseason games,
postponed and exhibition quarantine, late responses, duplicate/revised
official game IDs, previous-day midnight crossover and zero bet certification.
The existing preflight has no new recurring schedule; it is triggered by
source code or workflow edits and can be manually dispatched.

## Non-promotions / next steps

- **Verified direct DraftKings executable quote/market IDs: 0**
- **Verified native model probabilities: 0**
- **Certified Champion-001 and Challenger-001 predictions: 0**
- **Qualified chronological model training examples: 0**
- **Certified positive-EV bets and automated wagers: 0**
- **Champion-001 untouched and frozen**

The local SHA-256 receipt authenticates only the bytes saved in this run; it
does not establish a publisher-signed original publication timestamp.
League-specific scheduling is not evidence of player availability or sportsbook
settlement rules.

**Next development (#78):** League-operated NBA exact-scoreboard game-ID
crosswalk, with a fail-closed source outage path. After league identities,
separately build a directly observed bookmaker quote capture with exact sport,
event, market, selection, line, and price timestamps.
