# Challenger-001 — secondary NBA / MLB outcome review (research only)

This stage compares ESPN's archived completed-game rows against a separate league-operated publishing source. It does **not** independently verify historical pregame feature publication timestamps or license any training or betting recommendations.

- **MLB:** compare the existing ESPN August 2026 backfill to MLB StatsAPI schedule outcomes over the matching date window. One bounded MLB schedule request; compare both teams, start time (within six hours), unique game match, and final scores. Doubleheaders that cannot be uniquely matched are explicitly flagged.
- **NBA:** attempt to compare the ESPN February 2026 backfill with NBA.com's public schedule JSON if it still contains the target historical season. If not, try the documented no-key, independent **SportsBlaze 2025–26 season schedule archive** at `https://cache.sportsblaze.com/schedule/nba/2025`. SportsBlaze is a **third-party published source, not NBA.com or an official league adjudicator**. Check final status, exact home/away names, game time within six hours, unique identity and matching final scores. Any inaccessible, malformed, ambiguous, or unmatched record remains quarantined. Source provenance is included in the audit report.
- Input: latest successful **existing** historical backfill GitHub artifacts (not a new paid odds API collection).
- Output: `secondary_result_checks.jsonl` and `secondary_result_report.json` per league. Result statuses distinguish agreement, disagreement, ambiguous identity, and no secondary match.
- A second published source observed **today** is not a pregame snapshot from the historical date. No old feature gets a fabricated timestamp.
- Source failures and malformed input fail closed; all candidates remain quarantined.
- All counts for qualified training, certified Champion-001 or Challenger-001 predictions, betting-ready selections, and automated wagers remain zero. Champion-001 is unchanged.

Workflow: `.github/workflows/challenger-independent-results-audit.yml`. On a PR it executes offline tests only. On merge to main it reuses an existing backfill artifact, then attempts the cross-check for NBA and MLB with **zero SharpAPI, Sports Game Odds, or sportsbook requests**.

**Remaining dependency:** independently documented pregame feature availability, verified historical game identities and outcomes, sufficient continuous seasons, appropriately timed odds/lineup evidence, and rigorous out-of-sample evaluation. Do not rename the quarantined candidates to `historical_results.jsonl`.

**Fallback source documentation:** https://documentation.sportsblaze.com/schedule/ . This is a public archive, not evidence that its values existed before tipoff. Do not use published-source matches as historical pregame feature timestamps. ESPN remains the primary published-results source, so re-fetching ESPN does not count as independent corroboration.
