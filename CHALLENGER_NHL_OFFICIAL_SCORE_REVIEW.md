# Challenger-001: NHL-operated second-source final score crosscheck

Status: **Research only. Neither NHL score agreement nor preserved raw bytes qualifies a model or an actual wager.** Champion-001 remains frozen.

## What is implemented

This expands the existing eight-sport original-byte audit with an NHL-operated **second retrospective outcome source**. In the prospective outcome workflow, the script reads only NHL events that survived the original ESPN pregame byte/receipt integrity stage:

- For the **three latest** Eastern game dates with archived ESPN-published NHL finals, requests the public league-operated score source at \`https://api-web.nhle.com/v1/score/YYYY-MM-DD\`; no sportsbook, odds quota or proprietary paid provider used. Older dates are marked out of bounded scope rather than silently treated as checked.
- Requires source response \`currentDate\` to match the exact requested date, a structurally consistent list of games, unique NHL game IDs, valid scheduled start timestamps, complete home/away abbreviations and a safely parsed game state.
- Joins an archived ESPN event to NHL's game only if **exact full team names** map to the NHL IDs, home and away are not reversed, and scheduled start differs by no more than 30 minutes. Multiple matches remain ambiguous and are not chosen arbitrarily.
- Compares only \`OFF\` or \`FINAL\` games with numeric distinct final scores. Missing scores or in-progress games never qualify as agreements.
- Reports agreement, disagreement, unavailable/invalid NHL source, unjoined/ambiguous identities, missing prior ESPN final, or outside-coverage cases.
- Records the original raw NHL JSON response bytes for each successfully parsed source day and a SHA-256 per date in per-event reports. The original-byte hash detects later edits, **not the original publication date or an externally authenticated timestamp**.
- Records NHL final-period type (\`REG\`, \`OT\`, \`SO\`) as **retrospective research only**. It does not grade an NHL regulation-only bet, a three-way tie, a player prop or a sportsbook-specific moneyline settlement.

Historical and current names are kept in a narrow explicitly approved exact name dictionary; unknown aliases fail closed rather than fuzzy-matching teams.

## Inputs and outputs

\`\`\`bash
python challenger_nhl_official_score_crosscheck.py \
  --lineage prospective_validation/original_bytes_lineage_review.jsonl \
  --output-dir prospective_validation \
  --max-days 3

python -m unittest discover -s tests \
  -p 'test_challenger_nhl_official_score_crosscheck.py' -v
\`\`\`

Outputs:
- \`nhl_official_score_crosscheck.jsonl\`
- \`nhl_official_score_crosscheck_report.json\`
- \`nhl_original_source_responses/YYYY-MM-DD.json\` for successfully parsed source days.

The existing twice-daily \`challenger-prospective-outcome-validation.yml\` now executes the check **after** eight-league original-byte lineage. The PR and main workflows exercise all offline safety fixtures; network source failures produce explicit \`source_unavailable\` blockers, not invented scores. All files live in the existing 90-day research artifact (not durable storage).

## What remains unsolved

A league-owned result is useful independent *published-source* corroboration, **not independent proof of pregame feature publication time or a sportsbook's actual settlement**. NHL-sourced player box scores, historical player-level pregame usage/rosters/injuries, long-term immutable archive retention, verified game-by-game sportsbook prices and actual model probability forecasts remain unfinished.

NBA and MLB have their separate older second-source checks. NFL, NCAAF, NCAAB, MLS and UEFA Champions League still need distinct official/second-source result and market-definition adapters; avoid labeling this single NHL stage as complete eight-sport official adjudication.

There are **zero** automatically qualified training rows, calibrated model probabilities, certified picks, positive expected-value bets, or automated wagers from this step. Champion-001 is unchanged.
