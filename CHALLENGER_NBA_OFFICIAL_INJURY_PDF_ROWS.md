# Challenger-001 — official NBA injury PDF individual rows (research only)

## Purpose

Extend the existing NBA official injury-report original-byte archive to a conservative, **PDF-column-aware extraction of actual player injury designations**. The public injury report has columns for game date, time, matchup, team, player, status and reason. Player reasons can wrap across lines and reports can continue across pages; teams may instead say NOT YET SUBMITTED.

**This is NOT official active/inactive confirmation, sportsbook settlement or a verified player identity crosswalk.** An unlisted player, a team with an unsubmitted report, and even a reported Available player are not inferred to be confirmed active.

## Implementation and source integrity

- Reads ONLY the original NBA-owned injury PDF and HTML index already captured as observed, with exact SHA-256 bytes matching the capture report. Rejects changed bytes.
- Uses pdfplumber and actual PDF word x/y locations to avoid mapping a player's printed status to the wrong row. No OCR, heuristic player-name fuzzy mapping or inferred DNP.
- Validates the printed source PDF report time against the publisher-labeled PDF filename, without claiming publisher-signed publication timestamps.
- Accepts only exact NBA matchup codes, corresponding official team names and explicit reported player-status fields: Out, Doubtful, Questionable, Probable, Available.
- Preserves wrapped injury reasons and separates NOT YET SUBMITTED team reports. A missing team report cannot clear the entire roster.
- Preserves original player name and team but assigns NO NBA personId, ESPN athleteId or DraftKings player ID until an independently reviewed crosswalk exists.
- When a fresh prospective ESPN game archive exists, links only exact same Eastern game date and home/away team identities, after original report capture and before tipoff. Missing or ambiguous games stay unlinked.
- Any invalid table, duplicate source player, mismatched game/team, future timestamp, source mismatch or missing original PDF is blocked. No source evidence becomes a training row or bookmaker result.

## GitHub Actions

The scheduled NBA original injury PDF capture workflow now follows the PDF download with an individual-row parser. The existing successful prospective pregame evidence workflow also parses and links only future same-run games. Both install pinned pdfplumber from requirements-injury-pdf.txt.

From a successful original-source capture, run:

    python -m pip install -r requirements-injury-pdf.txt
    python challenger_nba_injury_pdf_player_rows.py --capture-dir nba_injury_current_original --output-dir nba_injury_current_original/player_rows_review

In a same-run pregame collector, also pass --events prospective_pregame/prospective_event_evidence.jsonl. Source evidence and output stay together in the short-retention GitHub Actions artifact, not signed external durable archival storage.

Generated research files:
- nba_injury_pdf_player_review.jsonl — individual league-report designations, matching state and explicit uncertified flags
- nba_injury_pdf_team_filings.jsonl — NOT YET SUBMITTED team report rows
- nba_injury_pdf_player_report.json — counts, schema blockers and zero qualification/certification counters

## Remaining blockers / next priority

1. Authenticated NBA personId / ESPN athleteId / DraftKings roster identity crosswalk with traded players and duplicate names handled.
2. Game-specific official pregame active/inactive lists and last-minute scratches, independently timestamped before the wager/prediction.
3. Independent pregame minutes, rotation/usage and role forecasts.
4. Exact bookstore-specific market terms, prices and prop settlements, independent chronological training/holdout, calibration and $0 pregame shadow outcomes.

All independently verified active players, player-prop training observations, trained prop models, certified Champion or Challenger picks, positive-EV bets and automated wagers remain zero. Champion-001 unchanged.
