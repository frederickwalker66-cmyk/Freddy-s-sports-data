# Challenger-001 — original NBA pregame injury report evidence capture

This adds the first **official NBA original-document prospective evidence archive** to the NBA player-prop research lane. It deliberately stops before automatic player injury status clearance, active lineup confirmation, player ID matching, predicted minutes or real-money odds.

## Verified real source

The NBA publishes its season injury-report index at:

https://official.nba.com/nba-injury-report-2026-27-season/

That index links frequent NBA-owned PDF snapshots under:

https://ak-static.cms.nba.com/referee/injury/Injury-Report_YYYY-MM-DD_HH_MMAM.pdf

The NBA explains that injury statuses can be updated continually on the same day. An earlier report is not proof of the final active lineup or minutes. Report time inside a filename is a **publisher label**, not an authenticated original server publication timestamp.

## New code

- challenger_nba_pregame_injury_pdf.py downloads the original official index HTML (2MB limit), parses only actual anchor links to the exact NBA static injury-report directory and filename syntax, and chooses only the newest PDF whose filename is no later than the actual observation time and no older than 24 hours.
- Download the selected PDF (12MB limit), verify basic PDF file signature and end marker, and preserve **exact original source bytes** plus SHA-256, original index bytes plus SHA-256, source URLs and the actual UTC observation timestamp. Basic PDF signature is not verification of contents, original authorship or an external signed receipt.
- If called with the fresh same-run ESPN prospective JSONL, attach one source-availability evidence record to each NBA event that has not started and whose existing original schedule snapshot is no older than six hours. This is not a claim that the PDF contains that exact game, player or team.
- All raw original bytes and event attachment reports are kept within the GitHub Actions artifact, limited retention (90 days). No archive gets a retrospective invented observation time. Invalid URLs, absent report, future report labels, DST clock ambiguity, stale games, missing source, invalid PDF bytes, duplicate game IDs or earlier promotions fail closed.
- **Every single event and player still has individual status/active lineup and player-prop eligibility equal to FALSE**. A player not mentioned in an injury report is NOT automatically considered active. Projected minutes and usage are not derived from the report.
- No sportsbook or paid odds provider is called.

## Workflow integration

- The existing challenger-prospective-pregame.yml now runs the PDF capture alongside each successful real prospective NBA evidence scan, using its original upcoming-game file. It ensures original PDF bytes and hashes match any report claims.
- A new independently scheduled .github/workflows/challenger-nba-injury-source.yml captures original league document bytes three times per day (14:00, 19:00, 23:00 UTC) even if no paid SharpAPI odds collector is active. It runs without a game list, so it does not falsely assert per-event coverage.
- The same standalone workflow can be run using GitHub Actions workflow_dispatch. Schedules may be delayed, so all timestamps use the actual code-observed UTC time; schedules are not evidence of exact request time.
- Pull requests run offline fixture tests only, not public network captures.

Inputs/outputs after an active same-run prospective game capture:

    python challenger_nba_pregame_injury_pdf.py \
      --events prospective_pregame/prospective_event_evidence.jsonl \
      --output-dir prospective_pregame/injury_report_original

The output directory includes nba_injury_original_report.json, nba_injury_event_attachments.jsonl and, only after actual successful source capture, nba_injury_original_index.html and nba_injury_original_report.pdf.

To test without network:

    python -m unittest discover -s tests -p 'test_challenger_nba_pregame_injury_pdf.py' -v

## Next development priorities

1. Extract individual player/club/game/status rows from the actual NBA official PDF with page layout review, then validate identity against separately captured NBA person IDs and team roster records. No string-only match or missing-team assumptions.
2. Independently verify official pregame active/inactive status, report changes/late scratches, and use source times earlier than tipoff and earlier than any model-generated prediction.
3. Add model-agnostic projected minutes/usage evidence, then separate player-prop distributions, chronological OOS calibration, independent DraftKings price/market settlement and $0 prospective shadow scoring.
4. Source permanence/independent external timestamp signing: the GitHub run ID and file hash alone are not proof of the NBA original publication time.

**No qualified player prop training examples, verified active players, certified Champion-001/Challenger-001 picks, positive-EV bets or automated wagers are created here. Champion-001 remains frozen and untouched.**
