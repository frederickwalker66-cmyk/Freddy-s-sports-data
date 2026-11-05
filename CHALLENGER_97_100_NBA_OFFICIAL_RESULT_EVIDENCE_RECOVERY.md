# Freddy's Picks AI — NBA original-result source recovery and evidence worklist (#97–100)

## New operational change

The November 5, 2026 live validation completed **53 NBA pregame feature/outcome
research candidates**, but the normal NBA-operated
\`cdn.nba.com/static/json/staticData/scheduleLeagueV2.json\` endpoint returned
an HTTP error. The primary report therefore had
**53 \`nba_official_source_unavailable\` rows** and **0** NBA-operated
second-source score agreements. This source access failure is not evidence
that pregame research features did not exist; it means those records lacked
a second NBA-operated final-score comparison within that run.

The project already had **47 directional, untrained, $0 NBA pregame research
picks** plus six neutral captures linked to 53 ESPN-published NBA results.
These do not authenticate trained Challenger-001 probabilities.

## #97–99: Date-scoped official NBA Stats V3 final-score fallback

New \`challenger_nba_published_daily_score_fallback.py\` tries **at most four**
most recent unique historical Eastern-calendar dates among the existing
NBA research candidates via the canonical NBA-owned
\`https://stats.nba.com/stats/scoreboardv3?GameDate=YYYY-MM-DD&LeagueID=00\`
source. It never queries unbounded history, guesses another URL, retries access
denials, or uses an odds API.

For each originally retrieved source day, it archives **exact original JSON
bytes** and computes a same-workflow SHA-256 fingerprint. It verifies the
NBA league ID, exact requested date, canonical 10-digit official NBA game ID,
known NBA team name + team-ID pairs, game date/time, final status, non-tied
plausible integer score and exact ESPN matchup/start time within 30 minutes.

A matching final result can be marked as a **two-publisher published-score
agreement for research only**. An NBA-vs-ESPN score conflict is quarantined.
A different earlier NBA source disagreement is never silently overwritten.
Access denial, malformed JSON, wrong day, unfinished status or missing game
remain explicitly unresolved. The script outputs:

- \`prospective_validation/nba_original_daily_score_fallback_review.jsonl\`
- \`prospective_validation/nba_original_daily_score_fallback_report.json\`
- \`prospective_validation/nba_date_scoped_original_final_scoreboards/*.json\`
  (only successfully retrieved actual original source bytes)

This fallback is now between the primary NBA final-score comparison and the
existing independent-history qualification audit. The latter examines
the augmented NBA result evidence, but **never marks it as independently
qualified training**.

## #100: Per-event qualification worklist

New \`challenger_nba_training_evidence_worklist.py\` performs a four-way
conservative join of genuine prospective NBA history review candidates,
NBA operated source result comparisons, existing five-part qualification
review flags, and genuine archived NBA research baseline ledger selections.

The worklist ranks individual cases by whether an NBA-operated published
score agrees, identifies missing third-party original pregame publication
and receipt custody, independent market settlement and independent reviewer
sign-off, and indicates whether the original pregame heuristic selection
can be tied to that same snapshot.

It fails on duplicate or orphan event IDs, contradictory second-source
claims, modified Champion, self-promoted independent-proof flags, changed
teams or score lines, and after-start forecasts. Nothing is converted to
\`historical_results.jsonl\`. Output:

- \`prospective_validation/nba_independent_evidence_training_worklist.jsonl\`
- \`prospective_validation/nba_independent_evidence_training_worklist_report.json\`

## Model boundary

- Historical NBA research candidate count on the last inspected run: **53**.
- Primary NBA-owned published score agreements: **0**, because source denied
  access. Date-scoped fallback actual agreement count is **run-dependent**,
  never presumed in advance.
- Qualified training count: **0**.
- Qualified holdout count: **0**.
- Current training target: **200 earlier qualified games + 50 later holdout
  games**. No accepted training or certified model predictions can be
  conjured from 53 unqualified cases.
- No authenticated Champion-001 executable; **Champion frozen**.
- No certified Challenger-001 prediction, direct executable DraftKings
  checkout quote, +EV selection or wager.

The scripts are run by the existing prospective-outcome workflow and therefore
do not create any new independent schedule. Review files are historical research
provenance only. Access-denied results are recorded without trying to bypass
the NBA provider's restrictions.
