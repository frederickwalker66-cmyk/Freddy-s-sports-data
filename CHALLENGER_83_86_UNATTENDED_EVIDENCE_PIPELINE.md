# Freddy's Picks AI — uninterrupted operational sequence #83–86

**Scope:** Finish the next engineering tasks automatically in order within an
existing GitHub preflight workflow. No recurring workflow is duplicated. No
Champion-001 model bytes, weights, probabilities or certified bets are altered.

## #83 — NFL independent *third-party* future schedule

- Fetch one bounded original nflverse/nfldata \`games.csv\` response if an actual
  future NFL game appears in the ESPN prospective archive.
- Validate full team IDs, season, week-style game identifier, Eastern kickoff,
  exact ESPN event ID if supplied, no recorded final scores, 60-second matchup
  alignment and actual pregame observation.
- Keep the exact original bytes and SHA-256 with observed UTC.
- NFLverse **is not NFL-operated**; it does not contribute to the existing
  NHL/MLB/NBA *league-operated* identity metric or prove feature availability.

Reference: nflreadr documents the nflverse schedule data as including future
games. Data is hosted at
\`https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv\`.
Blocked HTTP/CSV/clock/identity calls are reported as unverified, not retried
with invented fallback data.

## #84 — actual rolling pregame archive integrity

- Download up to four successful, previously archived source-run artifacts
  through GitHub Actions using read-only permissions.
- Verify each event's original ESPN schedule file SHA against original bytes,
  captured before its game start, and no altered model/positive-EV flags.
- Deduplicate by (league, ESPN event ID), not by raw capture count.
- Quarantine any team-side conflict or kickoff revision across source runs.
- Count actual unique future games **only as research identity observations**;
  200+ unique IDs do not prove 200 source-qualified training games.
- The ledger is retained with the same existing 45-day GitHub artifact limit,
  **not** durable publisher-signed third-party custody. Long-term immutable
  archival remains a separate external owner setup task.

## #85 — evidence-grounded operational priority queue

- Join actual #78 league-owned identity, #82 release, #83 independent
  third-party NFL source and #84 rolling original-byte ledger reports.
- Preserve source errors and enumerate next achievable technical steps.
- Explicitly distinguish prerequisite proof that only the owner or independent
  source can supply, including Champion-001 immutable original,
  time-locked pregame features, independently adjudicated results,
  separate player-prop models and direct executable sportsbook quotes.
- Block predictions, models and market promotion when those inputs are absent.

## #86 — validated chained execution

The existing eight-sport preflight now executes:
ESPN original bytes → official NHL/MLB/NBA identities → nflverse third-party
identity → rolling real-source ledger → #79 market quarantine →
#80–82 blocked training/calibration/release assessment → #85 priority queue.

This is still **research-only**. Zero native model artifacts were trained,
zero independently verified DraftKings quotes, zero certified Champion-001
or Challenger-001 predictions, zero proven +EV, and no automated wagers.

The live workflow result is independently checked *after merge*; synthetic
offline tests passing is never substituted for real HTTP source access.
