# Recovered ChatGPT Library evidence — Challenger-001 #88

Observed from user-owned ChatGPT Library ZIPs on November 5, 2026.
Source archive: eight-sport-historical-database.zip (archived October 31).
Original ZIP SHA-256:
046a6ab120cb3f0a9f8a6a75c44988673827dc244e1855a445ae0782494cc8d2

The archived SQLite was opened read-only and passed its integrity check.
All four files listed in its internal SHA-256 manifest matched their original
archived bytes. Local hashes are NOT independent publisher signatures,
immutable third-party custody or historical as-of pregame authentication.

| League | Distinct historical published-score games |
|---|---:|
| MLB | 426 |
| MLS | 63 |
| NBA | 241 |
| NCAAB | 373 |
| NCAAF | 283 |
| NFL | 71 |
| NHL | 193 |
| UEFA Champions League | 32 |
| **Total** | **1,682** |

- Accepted source windows: **32**, rejected source windows: **12**.
- Source observations: **6,728** (4 archived observations per game).
- **5,046** repeated source observations must not become extra games.
- All **6,728** source retrieval times were **after or at kickoff**.
  Postgame retrieval proves historic result access, NOT pregame feature access.
- All **1,682** final result rows have independent adjudication, bookmaker
  settlement and qualified-training flags **0**.
- The Champion original executable, immutable provenance and reference
  outputs were not authenticated.
- The independent holdout is empty. Certified OOS calibration groups: 0.
- Coverage consists of bounded windows rather than entire historical seasons.
  NBA has 241 unique archived final scores: below the nominal 250 raw-game
  target and none is qualified anyway.

A separate October 24 starter ZIP contains **94** older results and **511**
early-timestamp quote candidates, including **89 DraftKings-labeled** rows.
Every one of the 511 says pregame_confirmed=NO and
usable_for_model_backtest=NO. None is a direct executable DraftKings quote.
Do not add its games to the 1,682 without independent crosswalk and dedup.

## Reproduce with owner-controlled archive files

Run the read-only CLI without any sportsbook API:

    python challenger_library_archive_audit.py \
      --history-zip /path/to/eight-sport-historical-database.zip \
      --legacy-zip /path/to/Freddys_Picks_AI_Historical_Database_Starter_2026-10-24.zip \
      --output /path/to/challenger_88_library_history_audit.json

This script does NOT execute untrusted ZIP contents, update model bytes,
train Challenger, certify a bet, or place a wager. Source filenames are
research provenance, not direct sportsbook evidence.

Note: GitHub Actions cannot independently access the user's ChatGPT
Library ZIPs; the offline CI tests use synthetic fixtures only.
Actual ZIPs were inspected here in the user-requested ChatGPT workspace.

## Release outcome

Qualified historical pregame training records = 0.
Certified Champion-001 predictions = 0.
Certified Challenger-001 predictions = 0.
Verified direct bookmaker odds = 0. Certified positive EV = 0.
Automated wagers = 0. Champion-001 remains frozen.

Next external priority: independently verified as-of pregame features,
league-operated original outcome adjudication, market settlement rules,
disjoint chronological training/holdout evidence and verified model output.
Moneyline and player-prop models remain separate.
