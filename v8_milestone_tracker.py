"""V8 milestone reporting, built to fail closed without external audit evidence.

Two milestones:
A: functional, independently audited NBA forecasts.
B: independently audited all-eight-sport predictions and pricing.

This script NEVER assumes that a green CI run, a signed-looking hash, or a
self-reported review flag proves model skill, bookmaker execution or source
provenance. A human/third-party release review is required outside this code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LEAGUES = ("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab", "mls", "uefa_champions_league")
REQUIRED = (
    "independent_source_and_asof_audit",
    "independent_settlement_audit",
    "chronological_untouched_holdout",
    "reproducible_model_and_probability_audit",
    "calibration_and_market_baseline_review",
    "verified_executable_odds",
    "independent_release_signoff",
)
MIN_TRAIN = 200
MIN_HOLDOUT = 50


def _review_league(league, record):
    """Treat all supplied attestations as claims pending external review."""
    if not isinstance(record, dict):
        record = {}
    missing = [field for field in REQUIRED if record.get(field) is not True]
    for field, minimum in (("qualified_train_games", MIN_TRAIN),
                           ("qualified_holdout_games", MIN_HOLDOUT)):
        count = record.get(field)
        if type(count) is not int or count < minimum:
            missing.append(f"{field}_below_{minimum}")
    if record.get("champion_001_modified") is not False:
        missing.append("champion_001_frozen_not_attested")
    if league in ("mls", "uefa_champions_league"):
        if record.get("three_way_draw_and_regulation_rules_audited") is not True:
            missing.append("soccer_three_way_rules_not_audited")
    if record.get("market_scope") not in ("moneyline", "three_way_90_minute"):
        missing.append("market_scope_unverified")
    if league in ("mls", "uefa_champions_league") and record.get("market_scope") != "three_way_90_minute":
        missing.append("soccer_market_scope_mismatch")
    if league not in ("mls", "uefa_champions_league") and record.get("market_scope") != "moneyline":
        missing.append("binary_market_scope_mismatch")
    return {
        "league": league,
        "evidence_claims_satisfy_checklist": not missing,
        "independently_certified_by_this_script": False,
        "blockers": missing or ["external_evidence_must_be_independently_inspected"],
        "qualified_training_games_claimed": record.get("qualified_train_games") if type(record.get("qualified_train_games")) is int else 0,
        "qualified_holdout_games_claimed": record.get("qualified_holdout_games") if type(record.get("qualified_holdout_games")) is int else 0,
    }


def build_report(evidence=None):
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, dict) or any(key not in LEAGUES for key in evidence):
        raise ValueError("evidence must be a map keyed by the eight configured leagues")
    sports = {league: _review_league(league, evidence.get(league)) for league in LEAGUES}
    a = sports["nba"]["evidence_claims_satisfy_checklist"]
    b = all(r["evidence_claims_satisfy_checklist"] for r in sports.values())
    return {
        "version": "v8-elite-two-milestone-status-v1",
        "milestone_a_nba": {
            "engineering_evidence_checklist_passed": a,
            "independently_complete": False,
            "status": "external_review_required" if a else "blocked_missing_qualified_evidence",
            "remaining_blockers": sports["nba"]["blockers"],
        },
        "milestone_b_eight_sports": {
            "engineering_evidence_checklist_passed": b,
            "independently_complete": False,
            "status": "external_review_required" if b else "blocked_missing_qualified_evidence",
            "leagues_ready_for_external_review": [lg for lg, r in sports.items() if r["evidence_claims_satisfy_checklist"]],
        },
        "by_league": sports,
        "certified_predictions": 0,
        "certified_positive_ev_bets": 0,
        "bet_ready": False,
        "automated_wagers": 0,
        "champion_001_modified": False,
        "disclaimer": "Claims and self-issued checksums do not substitute for independent custody, pregame as-of verification, audited settlements, or real sportsbook checkout.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", help="Optional independently reviewed evidence manifest JSON")
    parser.add_argument("--output", default="v8_results/milestone_status.json")
    args = parser.parse_args(argv)
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8")) if args.evidence else {}
    report = build_report(evidence)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"milestone_a": report["milestone_a_nba"]["status"],
                      "milestone_b": report["milestone_b_eight_sports"]["status"],
                      "certified_predictions": 0, "output": str(target)}))


if __name__ == "__main__":
    main()
