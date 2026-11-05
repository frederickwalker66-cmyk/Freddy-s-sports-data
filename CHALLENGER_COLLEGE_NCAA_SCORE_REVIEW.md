# Challenger-001 college NCAA.com-derived results crosscheck

**Research-only. No certified training, probabilities, player props, expected-value selections or wagers. Champion-001 remains frozen.**

## Why this adapter exists

The old \`data.ncaa.com/casablanca/scoreboard\` URL must **not** be assumed to support 2026. The maintained [henrygd NCAA API](https://github.com/henrygd/ncaa-api) uses NCAA.com's 2026 GraphQL-backed scoreboard data and transforms it into a JSON \`games[].game\` representation. This is a **community-operated NCAA.com-derived proxy**, not a league-operated NCAA final-score API, cryptographically authenticated archive, or source of true sportsbook settlements.

A second independently published view from NCAA.com's data can corroborate ESPN's later-published score without establishing that the original features were available before the game. Source access and score agreements remain review evidence, not model training data.

## Supported league scopes

- **NCAAF**: Division I FBS only, \`/scoreboard/football/fbs\` for the **current NCAA week**. For historical scoreboards, an operator can use \`--football-year YYYY --football-week W\` explicitly. An ISO week number or a date-derived guess is forbidden; without the supplied NCAA season/week identifier, older events outside the current scoreboard may remain unmatched. FCS and other college levels are out of scope.
- **NCAAB**: Men's Division I only, at most **three latest game dates** from the archived ESPN research outcomes. Exact \`/scoreboard/basketball-men/d1/YYYY/MM/DD/all-conf\` routes. Women's basketball and other divisions require distinct models and feeds.

The workflow makes at most **four** NCAA proxy requests per run, only when matching archived college events with ESPN-published final results exist. All responses are bounded to 4MB. Source failures, schema changes, missing NCAA contest IDs or source 2026 incompatibilities remain explicit blockers.

## Event matching safeguards

1. Require an original pregame snapshot with matching internal archive bytes/receipt and quarantined evidence flags. No data is silently promoted.
2. Require a later ESPN final timestamp, intact scores, valid non-tie binary win label and matching home/away research identities.
3. Parse NCAA source \`games[].game\` with a unique \`gameID\`, \`gameState == "final"\`, both numeric scores, reliable epoch-based kickoff time and exact home/away *school names* from an explicit reviewed school-name crosswalk. Missing/uncertain schools remain unreviewed, with no fuzzy mascot-stripping or guessed institution identity.
4. Require the same home/away school identities and kickoff within **30 minutes**. Reject multiple NCAA matches and reversed home/away teams.
5. Compare ESPN and NCAA-derived published final scores only once independent evidence was actually retrieved. Preserve original response bytes, per-request SHA-256 and observation timestamp. Hashes are integrity checks, **not original publisher-attested times**.
6. Separate exact published-score agreement, mismatch, not-final, missing source, bad response/schema, unreviewed school name, ambiguous event ID, and older/out-of-scope NCAA scoreboard dates.

The initial manual school-name dictionary intentionally covers a subset of prominent FBS and men's D-I programs; it is **not complete Division I coverage** and is not a substitute for a verified per-school ID crosswalk.

## Outputs

\`\`\`bash
python challenger_college_ncaa_score_review.py \
    --lineage prospective_validation/original_bytes_lineage_review.jsonl \
    --output-dir prospective_validation --max-days 3

# Optional historical NCAA football week: must be verified externally first.
python challenger_college_ncaa_score_review.py \
    --lineage prospective_validation/original_bytes_lineage_review.jsonl \
    --output-dir retrospective_week_review \
    --football-year 2026 --football-week 10
\`\`\`

- \`college_ncaa_score_review.jsonl\`: per-event source status, NCAA contest identity, observed published scores, raw payload hash and certification blockers.
- \`college_ncaa_score_report.json\`: per-sport counts, request URLs/routes, missing/invalid source diagnostics and raw file SHA-256.
- \`college_ncaa_proxy_original_bytes/*.json\`: raw source bytes for each successfully parsed request.

The existing \`.github/workflows/challenger-prospective-outcome-validation.yml\` now executes this step after NBA/NHL/NFL source lineage and before the NBA history intake. Its GitHub artifact retention is temporary, not independent long-term evidence authentication.

## Remaining proof gates

Official NCAA-operated adjudication from a source fully separate from a web scraper; authenticated original publication times for every pregame feature; broader verified college team ID crosswalk; roster/lineup and player-stat history; exact DraftKings market settlement and real-time checkout odds; independent chronological train/holdout; out-of-sample calibration and prospective live validation.

This adapter adds **research corroboration**, not training authorization or any positive-EV certification.
