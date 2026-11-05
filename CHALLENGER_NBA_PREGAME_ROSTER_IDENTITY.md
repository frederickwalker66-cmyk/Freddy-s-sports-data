# Challenger-001: pregame NBA scheduled-game player ID candidate review

**Research only. Champion-001 frozen. No player is declared active from this feed and no sportsbook prop is certified.**

## New development priority

The NBA public liveData boxscore contains official NBA game ID, team IDs, player personIds, printed names and game-roster status fields. The earlier official NBA injury PDF source shows individual names and reported injury designations, but **neither single source establishes a verified DraftKings player ID or the final active/inactive list**. This stage connects both NBA-published sources prospectively, with game and team checks, retaining the NBA personId strictly as an ID *candidate*.

Sources:
- NBA league-owned season schedule: https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json
- NBA game-roster liveData: https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gameId}.json
- NBA injury PDF: original PDF bytes already collected from the NBA injury report index and stored in the existing as-observed prospective archive.

## Safety and provenance

- The original NBA injury PDF is re-read by the existing strict PDF column parser, and both original PDF/index SHA-256 bytes are checked against the stored same-capture receipt.
- Accept only a valid report with a time actually observed within 24 hours. All injury rows must retain the explicit no-training/no-betting flags. If a team report says NOT YET SUBMITTED, any contradictory same-team player entry blocks the archive.
- Fetch the original NBA-owned schedule only if the PDF contains explicit player rows. Match game date in US Eastern time, full home/away club identities and a unique **scheduled** NBA game ID. Started or finished games are not eligible.
- During a genuine prospective ESPN game scan, also require an existing same-run ESPN future schedule event matched by exact teams and Eastern date and a start time within **60 seconds** of the official schedule. Source snapshots must precede the run and game; stale or conflicting ESPN matches are excluded.
- Up to four eligible upcoming games are queried for the official NBA liveData game roster. Accept only a game in **scheduled status 1**, the correct 10-digit official game ID, the matching original scheduled tipoff (60-second tolerance), same home and away club names, and nonempty uniquely identified player arrays on each side. Retrieval finishing at or after tipoff is blocked.
- Exact normalized first/last name match **within the verified team and game** yields a *review candidate* for the NBA personId and teamId. Normalized names permit accent/punctuation variation but no fuzzy/surname-only guesses. Duplicates and re-used person IDs across clubs block the entire source.
- Preserve actual original NBA schedule and game-roster JSON bytes, receipt-time UTC and SHA-256. Self-issued receipt time, a same-run archive or a hash does NOT independently authenticate the source's historical publication time.
- The game-roster player status and not-playing reason may be retained **verbatim** but are not promoted to active/inactive clearance. An NBA roster listing does not prove the player actually appeared; an injury report entry marked Available is not proof of final lineup status.
- Missing league data, unsubmitted report, stale observations, game starts during retrieval, wrong teams, empty player arrays, unknown player names and mismatched sources remain explicit blockers; no absent player is imputed as OUT, DNP or healthy.

## Integrated continuous research workflow

The standalone three-times-daily official injury document workflow includes the bounded NBA-only game roster review, even when no paid odds feed exists. Its identity candidates are NBA-owned only and remain **unlinked to ESPN event IDs** without an independent prospective ESPN source.

The main prospective evidence workflow also invokes the same module with an actual future ESPN schedule artifact, enforcing the 60-second cross-source event clock. Both run only after successfully creating the original injury PDF archive, then store their output in the existing temporary GitHub Actions artifacts (90-day retention).

CLI example:

    python challenger_nba_pregame_roster_identity.py --capture-dir nba_injury_current_original --output-dir nba_injury_current_original/pregame_roster_id_review --max-games 4

For strict ESPN event crosswalk also provide the option:

    --events prospective_pregame/prospective_event_evidence.jsonl

Output files:
- nba_pregame_roster_identity_review.jsonl — source game and player ID candidate, original injury report status and exact reason for no match
- nba_pregame_roster_identity_report.json — game coverage, per-source observation and hash, explicit unqualified/certification counts
- nba_roster_original_source_bytes/*.json — original as-observed NBA schedule and scheduled-game roster bytes only when truly fetched

## Subsequent priorities

1. Independently verify the league's game-specific **final active/inactive roster** and late scratches near tipoff. An injury report, preliminary roster, or game starter list is not equivalent to the official complete active list.
2. Review NBA personId ↔ ESPN athleteId ↔ DraftKings player ID with a separate source ID mapping, team transfers and duplicate-name collision handling. Match precision is not proven by same-name coincidence.
3. Add timestamped independent projected minutes, role/usage and actual game status BEFORE the model emits its selection. Never fill historical pregame features with retrospective box score minutes.
4. Obtain exact market-specific sportsbook terms and pregame quotes, independent prop settlement adjudication and out-of-sample calibration before allowing any positive EV certification or wager.

All automatically qualified player-prop training observations, active-player clearances, verified cross-platform ID mappings, certified picks, positive-EV bets and wagers remain ZERO. Champion-001 unchanged.
