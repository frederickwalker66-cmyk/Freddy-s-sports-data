"""Fail-closed MLB/NBA evidence inventory. No model execution or promotion."""
import argparse
import json
from pathlib import Path

LEAGUES = ("mlb", "nba")
REQUIRED = ("historical_pregame_feature_timestamps_verified",
            "historical_odds_snapshots_verified",
            "independent_result_adjudication_verified",
            "bookmaker_market_settlement_verified")

def audit(root):
    root = Path(root)
    result = {"stage": "mlb_nba_independent_source_gate", "status": "HOLD",
              "independent_source_authentication_performed": False,
              "qualified_training_rows_created": 0, "certified_take_predictions": 0,
              "champion_001_modified": False, "nfl_collection_modified": False,
              "leagues": {}}
    for league in LEAGUES:
        historical = []
        providers = []
        errors = []
        for path in sorted(root.rglob("backfill_coverage.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
                if item.get("league") == league:
                    historical.append(item)
            except (ValueError, OSError, TypeError) as exc:
                errors.append({"file": str(path), "error": type(exc).__name__})
        for path in sorted(root.rglob("validation_report.json")):
            if league not in path.parts and not any(league in p for p in path.parts):
                continue
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
                providers.append(item)
            except (ValueError, OSError, TypeError) as exc:
                errors.append({"file": str(path), "error": type(exc).__name__})
        failures = sorted({gate for item in historical for gate in REQUIRED
                           if item.get(gate) is not True})
        if not historical:
            failures.append("missing_historical_coverage_report")
        if not providers:
            failures.append("missing_league_provider_validation_report")
        if any(p.get("provider_scores_stats_odds_authenticated") is not True
               for p in providers):
            failures.append("provider_quantitative_authentication_missing")
        # A self-reported true flag is not independent proof. No record-level
        # pregame receipts, source signatures or settlement attestations are
        # evaluated by this inventory; it can NEVER certify training rows.
        failures.append("record_level_independent_attestations_not_evaluated")
        result["leagues"][league] = {
            "status": "HOLD", "historical_reports": len(historical),
            "provider_reports": len(providers),
            "published_final_observations": sum(max(0, int(x.get("published_completed_game_results", 0))) for x in historical),
            "quarantined_candidates": sum(max(0, int(x.get("quarantined_research_candidates", 0))) for x in historical),
            "blocking_gates": sorted(set(failures)),
            "parse_errors": errors, "qualified_training_rows": 0}
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.archive_root)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    assert report["qualified_training_rows_created"] == report["certified_take_predictions"] == 0

if __name__ == "__main__":
    main()
