# Challenger-001 — eight-sport original evidence and second-result coverage

This development step makes eight-league source completeness visible in one honest audit instead of implying a game result, a passing unit test, or a self-generated checksum is a winning, independently calibrated betting model.

## Scope

One row for each of exactly eight competitions:

| Sport | Current separate published-result path | Source classification |
|---|---|---|
| NBA | League-owned official final scoreboard review when NBA history candidate is independently matched | NBA-operated, retrospective |
| NFL | nflverse published schedule/score | Independent community publisher, not NFL-operated |
| MLB | Not integrated in this specific cross-source validation pipeline | Explicit missing result-adjudication stage |
| NHL | League-owned NHL game score | NHL-operated, retrospective |
| NCAAF | NCAA.com-derived source through henrygd proxy | Separately published third-party proxy, not NCAA-operated |
| NCAAB | NCAA.com-derived source through henrygd proxy | Separately published third-party proxy, not NCAA-operated |
| MLS | API Ninjas regulation score when accessible | Unaffiliated third-party score, not MLS-operated |
| UEFA Champions League | API Ninjas regulation score when accessible | Unaffiliated third-party score, not UEFA-operated |

MLB is NOT called independently verified just because an ESPN-published final exists. NBA's late historical score candidate stage is similarly NOT a model-ready pregame feature archive, even if NBA-owned scores agree with ESPN.

## How the audit works

1. Read original_bytes_lineage_review.jsonl created from actual archived prospective pregame events and same-run original-byte SHA receipts. Require valid league, unique event ID, source digests, original snapshot before tipoff, later observed published final, and all no-train/no-bet source-review flags.
2. Read completed score-review JSONL files from NBA, NFL, NHL, both NCAA sports, MLS and UEFA. Match only the exact league + original ESPN event ID. A league's second-source event not in the receipt-backed original subset is **quarantined**, not counted as a valid pregame observation or retroactively attached by fuzzy team name.
3. Distinguish: originally archived game evidence, available historical team-form features, linked ESPN results, separately reviewed published score, cross-source published-score agreement, disagreement and missing source rows. Any repeated original event ID, repeated second-source event or falsely promoted bet/training flag raises a validation error.
4. Always report *zero* independently authenticated original feature publication timestamps, bookmaker market settlement, qualified chronological training records, certified model probabilities, EV-positive bets, player prop models and wagers. A published-score agreement is retrospective corroboration ONLY, never an original pregame forecast or independent sportsbook settlement.
5. Each league gets a concrete evidence priority chosen from missing original snapshot, missing linked result, missing second-source coverage, source disagreement/unavailability, or unfinished publication/settlement authentication. These are evidence workflow blockers, not estimated win probabilities.
6. Save the read-only eight_sport_source_coverage.json alongside all original reviews in the existing 90-day GitHub Actions prospective outcome artifact. Do not generate historical_results.jsonl, eligible training inputs, Champion-001 probabilities or auto-bets.

Run after the actual cross-source comparison stages:

    python challenger_all_sports_source_coverage.py --input-dir prospective_validation --output prospective_validation/eight_sport_source_coverage.json

Regression coverage:

    python -m unittest discover -s tests -p 'test_challenger_all_sports_source_coverage.py' -v

The workflow also asserts each league's second-source row count cannot exceed its original snapshot count, agrees cannot exceed reviewed second-source rows, and every training/EV/certification counter remains exactly 0.

## Follow-on all-sport priorities

1. Repair missing original pregame event capture and extend independently published historical outcome adjudication by sport (especially MLB) using authorized sources. Preserve original bytes with actual capture clock and a source-publisher authenticity path.
2. Independently verify soccer 90-minute regulation and market-specific extra-time/shootout settlements, and NHL overtime/shootout market definitions before converting any outcomes into historical labels.
3. Establish per-league verified bookmaker/exchange pregame quote snapshots and source publication times, 200+ qualified per-market chronological training examples and 50+ clean holdouts before training separate models. NFL, NCAA, NBA and NHL games and all player props need distinct models/markets; do not pool eight sports into a fake model.
4. Recheck Brier score, log loss, calibration, CLV and realized ROI where there is authentic out-of-sample evidence; do not confuse synthetic test performance with betting accuracy.

Champion-001 remains frozen and no new certified picks or positive-EV wagers are created.
