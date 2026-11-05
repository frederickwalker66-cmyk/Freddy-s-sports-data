# Challenger-001: eight-sport original-byte lineage and blockers

## Priority delivered

Adds an automated **research-only original-byte evidence audit** to the existing twice-daily prospective outcome validation workflow.

The system already had same-run SHA-256 receipts and automatic ESPN result linkage. Previously, it did not produce a per-event audit dossier that joined a specific original archived row, original archive bytes, original receipt, point-in-time team-form features, and later published result. This feature closes that operational gap **without pretending to independently certify history**.

## How it works

1. Scan archived pregame evidence inside numeric GitHub Actions run ID folders (e.g. `snapshots/12345/`). Require `prospective_event_evidence.jsonl` and `point_in_time_receipt.json` from the *same* archive.
2. Verify unmodified raw bytes and every individual JSONL record against its same-run recorded SHA-256. Reject malformed receipts, incorrect run IDs, tampering, late-game captures, and conflicted earliest snapshots.
3. Select the earliest original valid pregame snapshot for each unique league/event ID; preserve original-file SHA, original-line SHA, receipt SHA, run ID, timestamp and source URLs in a review packet.
4. Link to at most one consistent published result for the identical event. Never fabricate missing or contradictory scores, or treat ESPN's published finals as independently adjudicated sportsbook settlements.
5. Copy the four authentic *recorded-at-the-time* team-form research features only when both original form records pass validation; absent or late form remains missing rather than filled with zeros.
6. Flag exact blockers for independent capture authentication, original feature publication/as-of verification, outcome adjudication and book-specific market settlement. Soccer three-way **90-minute** result requires separate verification; full-game results cannot be silently used as regulation-only outcomes.

Eight configured leagues: NBA, NFL, MLB, NHL, NCAAF, NCAAB, MLS, UEFA Champions League.

## Generated files

- `prospective_validation/original_bytes_lineage_review.jsonl`: per-game review dossier with exact original-byte provenance and `missing_evidence` blockers.
- `prospective_validation/original_bytes_lineage_report.json`: archive-level tampering/missing-receipt counts plus league-level availability and blocker coverage.

**Both artifacts are for human/source review only.** They deliberately use a different record schema from `challenger_reviewed_pregame_games.jsonl` and cannot be fed straight into `challenger_multisport_native_training.py`. No positive evidence flags are populated automatically; an internal SHA or a GitHub run ID is not a trustworthy independent publication timestamp.

## Run manually

```bash
python challenger_multisport_original_bytes_lineage.py \
  --snapshot-root snapshots \
  --linked-results prospective_validation/linked_pregame_outcomes.jsonl \
  --output-dir prospective_validation

python -m unittest discover -s tests -p 'test_challenger_multisport_original_bytes_lineage.py' -v
```

The existing `challenger-prospective-outcome-validation.yml` workflow now runs this step **after** the published-outcome link is built and before downstream NBA candidate review. It runs the complete offline regression suite on PRs; the scheduled job uses previously archived original event snapshots and current/archived ESPN final result observations.

**Not yet solved:** verifying original provider publication independently of the author's own capture, league-operated settled market outcomes for all eight leagues, authenticated injury/availability data, player prop historical as-of features, preserving archived artifacts beyond GitHub retention, producing 200+50 qualified rows per league, and calibrating fresh independent prospective forecasts.

No automatic model training, deployed probability forecasts, market-priced positive EV, wagers, or Champion-001 changes are authorized.
