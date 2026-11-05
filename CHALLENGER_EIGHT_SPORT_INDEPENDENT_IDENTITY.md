# Challenger-001 Upgrade #76 — independent game identity gate

## What changed

Building on #75's actual original ESPN schedule byte capture, the same
read-only, one-time main-branch preflight now obtains a **separate NHL-operated
original scoreboard response** for each Eastern date containing archived NHL
pregame games. It saves the untouched NHL bytes, response observation time,
source URL and SHA-256. The existing twice-daily all-sports schedule and
Champion-001 remain unchanged.

Archived NHL games only earn the
`nhl_exact_pregame_game_identity_agrees_research_only` diagnostic when:
- the archived ESPN row is unique, pregame, and unmodified;
- an NHL-operated raw response was actually captured and parsed, at/after the
  ESPN archive but **before** the game's kickoff;
- the NHL official full team abbreviation mapping agrees on both exact sides;
- exactly one official NHL game starts within **60 seconds** of ESPN's kickoff;
- a single official NHL event is not assigned to multiple ESPN IDs.

Missing network access, wrong day, bad bytes, duplicate game, swapped sides,
late capture, or a kickoff mismatch are quarantined and never promoted.

The same manifest reviews **all eight sports**. NBA, NFL, MLB, NCAAF, NCAAB,
MLS, and UEFA Champions League explicitly remain
`official_league_adapter_not_available` until each receives a real
league-operated pregame schedule adapter. Even NHL's match is only independent
source corroboration at fetch time: response hashes are locally computed,
not publisher-signed historical publication attestations.

## Files

- `challenger_eight_sport_independent_identity.py`
- `tests/test_challenger_eight_sport_independent_identity.py`
- Updated `.github/workflows/challenger-eight-sport-source-preflight.yml`

The existing 45-day workflow artifact gains:

- `independent_identity/independent_game_identity.jsonl`
- `independent_identity/independent_game_identity_report.json`
- `independent_identity/nhl_official_YYYYMMDD.json` for genuine NHL responses.

## Test locally

```bash
python -m unittest discover -s tests -p 'test_challenger_eight_sport_independent_identity.py' -v
```

## Important non-promotions

- **Direct DraftKings checkout / exact betting market verification: 0**.
- **Independently generated, auditable native model probabilities: 0**.
- **Certified Champion-001 / Challenger-001 picks: 0**.
- **Verified positive-EV bets and automated wagers: 0**.
- NHL source identity is not an active player check, verified moneyline
  (full-game vs regulation) or player prop settlement rule.
- Champion-001 is frozen and no historical training qualification is inferred.

## Next development priority (#77)

Extend this exact original-byte and actual-response-time contract to other
league-operated pregame schedules, with per-league time-zone and team-ID
crosswalks, before attempting the separate direct sportsbook market-ID and
quote freshness capture. Do not infer league status, actual betting odds,
or forecast calibration from ESPN schedule receipts.
