# Challenger-001: MLS + UEFA 90-minute result scope review

**Research-only. Does not change Champion-001, certify a pick, infer model probabilities, or authorize wagers.**

## Why this matters

A soccer three-way 1X2 market is home / draw / away at the end of the second half including stoppage time (90 minutes). Knockout ties may go to extra time or penalties. A team advancing after extra time or a shootout is NOT necessarily the 90-minute winner. Published full-match/advancement scores from ESPN alone cannot label every MLS playoff or UEFA Champions League 1X2 outcome.

The adapter consumes only previously archived pregame original-byte lineage packets; no historical game is reconstructed as pregame evidence.

## Separate publisher source

The optional external source is [API Ninjas Football (Soccer) API](https://api-ninjas.com/api/football), an unaffiliated third-party publisher, with one endpoint supporting league=mls and league=ucl. It exposes match period_scores, decided_in, and penalty_scores. It is NOT MLS-/UEFA-operated adjudication, DraftKings settlement, or a guaranteed original historical as-of snapshot.

- MLS uses match date in America/New_York; UEFA uses Europe/Berlin calendar dates.
- At most three newest archived game dates per league (six requests total).
- The workflow reads the optional GitHub Actions repository secret named API_NINJAS_KEY. If absent, it makes ZERO provider requests and reports external_api_key_not_configured. It does not imply the key already exists.
- Source response bytes per date are bounded to 3 MB, validated and SHA-256 recorded. Valid original raw bytes are retained inside the temporary GitHub artifact.
- Identity: same league, exact home and away club names with a small reviewed alias map, source unique match ID, start time within 30 minutes, and no single provider match reused for multiple ESPN events.
- Require final game state, chronologically valid updated_at, two separate regulation halves, and full match scores consistent with all recorded periods. For extra time, require four halves. For penalties, require separate penalty scores; they are never added to football goals.
- Derived source_regulation_90min_result uses the first TWO halves only, never the tournament winner or penalty scores.
- Normal full-time 90-minute finishes compare second-source score with ESPN. After extra time or shootouts, a full-match score agreement does NOT qualify independent 90-minute source corroboration; it is explicitly marked as secondary-only.
- Missing keys, malformed responses, missing period scores, unknown identities and timeline inconsistencies fail closed. Nothing becomes a training label automatically.

## Integration and output

The existing workflow .github/workflows/challenger-prospective-outcome-validation.yml executes this step after college second-source reviews and runs offline safety tests on pull requests. In the repository's GitHub Actions settings, an API_NINJAS_KEY repository secret can enable live-source review without exposing the value to code or logs. Do not commit or paste keys.

Manual command:

    python challenger_soccer_regulation_review.py --lineage prospective_validation/original_bytes_lineage_review.jsonl --output-dir prospective_validation

    python -m unittest discover -s tests -p 'test_challenger_soccer_regulation_review.py' -v

The script writes soccer_90min_second_source_review.jsonl and soccer_90min_second_source_report.json. Valid source bytes are saved under soccer_second_source_original_bytes/. GitHub artifact retention is temporary, not independently authenticated archival storage.

## Unfinished dependencies

League-operated independent regulation-time adjudication, original independent pregame feature timestamps, bookmaker-specific settlement, verified DraftKings checkout quotes, authentic trained pregame model probabilities, minimum chronological training/holdout coverage, and out-of-sample calibration.

Champion-001 remains frozen. This module produces ZERO certified Champion picks, certified Challenger picks, independently qualified training games, positive-EV bets or automated wagers.
