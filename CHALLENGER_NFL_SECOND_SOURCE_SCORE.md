# Challenger-001 NFL second-source results cross-check (research only)

Status: **Separate published-score corroboration only. No model training, odds qualification, certified predictions or wagers. Frozen Champion-001 is unchanged.**

## Scope

The NFL comparison reads original vetted-by-internal-SHA research packets from \`challenger_multisport_original_bytes_lineage.py\` and fetches **one** third-party nflverse \`games.csv\` release from:

\`https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv\`

nflverse is a community-maintained published schedule/results source, **not an official NFL adjudicator**, and certainly not a recorded original pregame feature source. This is separate from ESPN's published score feed, so agreement is useful research corroboration, not independent market settlement.

The collector uses at most one external download (bounded to 15MB), has a maximum of 120 NFL lineage events per run, and parses completed game scores only for seasons 2024 onward. Missing, stale, invalid, unexpectedly formatted or inaccessible source files fail closed, and future games with blank results are not treated as losses.

For each NFL pregame event:
- Require one valid original-byte lineage packet, a prior captured timestamp, exact ESPN event ID and exact full-name home/away NFL teams.
- Convert nflverse's \`gameday\` + Eastern \`gametime\` to an aware UTC instant (including daylight-saving changes).
- Match only the same home/away abbreviations and kickoff timestamp within 30 minutes. If nflverse contains a non-null ESPN ID, it **must** equal the archived ESPN event ID.
- Reject duplicate game IDs, unsupported game types, malformed scored rows, ambiguous candidate matches, and contradictory event timing.
- Compare final scores. Never treat an NFL tie as a resolved two-way sportsbook moneyline result; report \`tie_requires_book_specific_settlement_review\`.
- Preserve the exact original nflverse CSV bytes, retrieved timestamp and SHA-256 for audit review. The hash does not authenticate previous release versions or establish a source's publication time.

This does not infer historical point-in-time features from the release's score, QB, betting lines, or closing prices. It does not score player props or ingest nflverse odds into an independent model.

## Execute

\`\`\`bash
python challenger_nfl_secondary_score.py \
  --lineage prospective_validation/original_bytes_lineage_review.jsonl \
  --output-dir prospective_validation

python -m unittest discover -s tests \
  -p 'test_challenger_nfl_secondary_score.py' -v
\`\`\`

Outputs in \`prospective_validation\`:
- \`nfl_second_source_score_review.jsonl\`
- \`nfl_second_source_score_report.json\`
- \`nflverse_original_games.csv\` only after successful source parsing

The scheduled \`challenger-prospective-outcome-validation.yml\` runs this step after the original-byte lineage audit and NHL second-source results check. GitHub Actions archives have finite retention, not immutable long-term storage.

## Remaining validation work

- Verify original published data *as of* the pregame timestamp using external trustworthy capture or source publication metadata.
- League-operated independent NFL result adjudication, exact sportsbook rule and payout grading, team/player injury availability and authenticated historical prop statistics.
- College football and men's college basketball: use NCAA's current 2026 data structure; some legacy NCAA Casablanca scoreboard URLs stopped being reliable for 2026. A source adapter must verify original source schema and date before being added, rather than silently treating missing 2026 data as zero results.
- MLS/UEFA three-way 90-minute outcome independently adjudicated before soccer calibration.
- Genuine 200 chronological training and 50 later independent holdout events **per league**, and fresh prospective forecast receipts before calibration.

All certification/selection counters stay zero. Research source agreement is not approval to train or place a bet.
