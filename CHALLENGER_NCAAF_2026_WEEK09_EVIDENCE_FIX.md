# Challenger-001 — NCAAF Historical Week 09 and Exact School Identity Repair

## Root cause identified in real eight-sport source archives

GitHub run 42063232096 included 47 receipt-backed October 31, 2026 NCAAF games, with 43 reported unreviewed school identities, four unmatched contests, and zero corroborated results. Inspection of the original NCAA.com-derived source bytes showed the code had requested the CURRENT week's November 3–7 games, not the historical October 31 games.

Official NCAA.com scoreboard confirms October 31, 2026 games in FBS Week 09:
https://www.ncaa.com/scoreboard/football/fbs/2026/09

The third-party NCAA.com-derived API documents YEAR/WEEK football scoreboard paths:
https://ncaa-api.henrygd.me/openapi

## Changes

1. An explicit verified 2026-10-31 Eastern -> season 2026, Week 09 map selects the historical NCAA.com-derived source at https://ncaa-api.henrygd.me/scoreboard/football/fbs/2026/09/all-conf. No ISO-week inference.
2. A current-week query is only a fallback for a game from today or yesterday Eastern. An older unreviewed week, or mixed known/unknown prior week dates, does NOT request current-week data. It records a missing independently reviewed source week instead.
3. Added 72 exact ESPN team display identities and 71 exact NCAA.com-derived source-short aliases from reviewed 2026 FBS team-name conventions. No fuzzy team names, mascot substring inference, or Miami Florida/Ohio conflation.
4. The proxy's actual 2026 startDate format MM/DD/YYYY is accepted alongside YYYY-MM-DD and strictly checked against the actual game epoch/date, instead of silently ignoring it.
5. Continues to enforce strict home/away identity, unique game ID, 30-minute clock tolerance, completed score, raw response SHA-256 and actual observation time. No historical pregame feature publication or bookmaker settlement is inferred.
6. New tests validate historical Week 09 route, team aliases, distinct institutions, impossible dates, reversed teams, nonfinal results, wrong clock, unreviewed historical weeks and zero-bet assertions.

## What this does NOT mean

An independently published NCAA.com-derived retrospective score agrees or disagrees with ESPN; it is NOT NCAA-operated official outcome adjudication, authenticated historical bookmaker settlement, or proof of an actual pregame model prediction.
Only the first post-merge real historical Week 09 fetch can establish live source agreements. No training records or certified bets are created; Champion-001 is unchanged.

Other all-sports follow-on: diagnose absent NFL, MLB, NCAAB and UEFA pregame records against actual game calendars (never force no-game days); NHL has ten reviewed source-score agreements but lacks independent feature timestamps and market settlement; MLS requires independent 90-minute market and source-key validation.
