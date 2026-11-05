# Challenger-001: NBA official injury-report revision monitoring (research only)

**Purpose:** Detect when NBA team injury designations change between two authentic NBA-owned PDF snapshots. This is a published-report revision monitor, **not** a certified official active/inactive list, a confirmed late scratch, a sports betting settlement or a pregame-trained model.

The NBA says official injury reports are updated continuously during the day. Its 2026–27 injury report site lists PDF revisions with printed date/time labels; some teams have NOT YET SUBMITTED filings and the report is not a complete proof of a team's game-day active roster.

## Original evidence and clocks

The module challenger_nba_injury_revision_monitor.py:

1. Takes the NBA original index HTML, latest PDF and source receipt already downloaded in a same-run real capture by challenger_nba_pregame_injury_pdf.py. Rechecks the original raw index and PDF against their SHA-256 receipts and explicitly requires all no-certification flags.
2. Reads only canonical NBA-owned PDF URLs linked by the existing index; selects the immediately previous source-label revision within 90 minutes. If none exists, reports a missing comparison rather than claiming a player was healthy. The latest link must still be the same link the initial archive selected.
3. Downloads the previous PDF **at the current run time** from NBA-owned static media, checks a bounded PDF signature/size, preserves its untouched bytes and SHA-256, and parses BOTH PDFs with the existing pdfplumber column-aware NBA parser.
4. The older report filename label is NOT assumed to be the time at which the collector actually observed that source. The report stores both publisher labels and the real time the earlier PDF was fetched. It never claims independently authenticated historical publication.
5. Compares the same Eastern game date, exact matchup, NBA team code, and exact normalized player name. Only explicit changes between two printed rows count as designation changes. It separates changes to Out, changes from Out, other changes, newly listed players, and names missing from the newer PDF. Absence from a report is **not** proof of active eligibility, injury recovery or an under result.
6. Explicit NOT YET SUBMITTED team filing entries are not converted into cleared players. Duplicated player names within a team/game, contradictory missing filings, corrupted source signatures or unstable clocks fail closed.
7. In the same-run prospective workflow, an observed change to Out may be flagged for *manual review* only if a single upcoming ESPN game matches the exact game date/opponents and the newer report was actually captured before tipoff. Even then, a designation change is NOT an independently confirmed late scratch or player-prop settlement.
8. Every result and report retains false active/inactive clearance, model training, bookmaker market eligibility, prediction and wager flags. Champion-001 is frozen.

## Workflow integration and frequency

- The original NBA injury-source workflow now captures the source once each morning and approximately every 30 minutes during the evening NBA window via GitHub Actions schedule (17:00–03:30 UTC plus 14:00 UTC). GitHub cron can be delayed, which is why actual download timestamps—not planned schedule times—control all evidence gates. No additional paid odds provider is used. The increased frequency also means more GitHub Actions usage and short-retention artifacts.
- The same-run eight-sport prospective evidence workflow also executes this comparison after collecting the NBA PDF and game roster, using actual prospective ESPN game identities.
- Both preserve the previous PDF within the existing GitHub Actions artifact (normally 90-day retention) and verify that its stored bytes match the reported SHA-256.
- A source failure/missing prior PDF is a noncertifying blocker, not a failed bet or a negative result.

Manual operation after a successful original NBA PDF capture:

    python challenger_nba_injury_revision_monitor.py --capture-dir nba_injury_current_original --output-dir nba_injury_current_original/revision_monitor

With fresh prospective ESPN game artifacts:

    python challenger_nba_injury_revision_monitor.py --capture-dir prospective_pregame/injury_report_original --events prospective_pregame/prospective_event_evidence.jsonl --output-dir prospective_pregame/injury_report_original/revision_monitor

Output:

- nba_injury_status_changes.jsonl — source-designation revisions with explicit earlier/later reports and uncertified flags
- nba_injury_revision_report.json — comparisons, change counts, uncertainty, source hashes and blockers
- nba_previous_original_injury_report.pdf — source predecessor original bytes, only after both sources parsed successfully

## Still blocked

A separate authenticated official complete active/inactive roster shortly before tipoff; NBA personId ↔ ESPN athleteId ↔ DraftKings ID crosswalk; late scratch settlement and void rules; original publisher-authenticated pregame timestamps; independently verified minutes, usage, line/price and historical player-prop settlements; minimum chronological holdout and actual calibrated pregame forecasts.

**No automatic training examples, certified Champion or Challenger predictions, verified positive-EV selections or bets are created by this module.**
