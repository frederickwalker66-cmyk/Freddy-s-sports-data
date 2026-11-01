"""Fail-closed Challenger training-readiness inventory; never modifies Champion-001."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from challenger_backtest import LEAGUES, timestamp, validate_record

MIN_TRAIN, MIN_HOLDOUT = 200, 50

def assess(rows):
    accepted, rejected = {}, Counter()
    for row in rows:
        try:
            validate_record(row)
            if row.get("qualified_for_challenger_backtest") is not True:
                raise ValueError("not_independently_qualified")
            if row.get("independent_pregame_source_audit") is not True:
                raise ValueError("pregame_source_audit_missing")
            if row.get("independent_outcome_adjudication") is not True:
                raise ValueError("independent_outcome_audit_missing")
            key = (row["league"], str(row["event_id"]))
            if key in accepted:
                raise ValueError("duplicate_event")
            accepted[key] = row
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            rejected[str(exc)[:100]] += 1
    per_league = {}
    for league in sorted(LEAGUES):
        group = sorted((r for (lg, _), r in accepted.items() if lg == league),
                       key=lambda r: (timestamp(r["start_utc"]), str(r["event_id"])))
        cut = int(len(group) * .8)
        holdout = group[cut:]
        first_holdout = min((timestamp(r["snapshot_utc"]) for r in holdout), default=None)
        eligible = [r for r in group[:cut]
                    if first_holdout and timestamp(r["outcome_verified_at_utc"]) <= first_holdout]
        schema_ok = bool(group) and all(set(r["features"]) == set(group[0]["features"]) for r in group)
        ready = (schema_ok and len(eligible) >= MIN_TRAIN and len(holdout) >= MIN_HOLDOUT
                 and len({r["outcome"] for r in eligible}) == 2
                 and len({r["outcome"] for r in holdout}) == 2)
        per_league[league] = {
            "accepted_independently_audited_records": len(group),
            "eligible_chronological_training_records": len(eligible),
            "later_holdout_records": len(holdout),
            "additional_training_records_needed": max(0, MIN_TRAIN - len(eligible)),
            "additional_holdout_records_needed": max(0, MIN_HOLDOUT - len(holdout)),
            "consistent_feature_schema": schema_ok,
            "research_training_ready": bool(ready),
        }
    return {
        "stage": "challenger_training_readiness_gate",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "by_league": per_league, "rejected": dict(sorted(rejected.items())),
        "qualified_training_examples": sum(v["eligible_chronological_training_records"] for v in per_league.values()),
        "leagues_ready": [k for k,v in per_league.items() if v["research_training_ready"]],
        "certified_predictions": 0, "bet_ready_selections": 0,
        "champion_001_modified": False,
        "warning": "Boolean audit flags are declarations, not independent proof; manual provenance verification remains required.",
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="historical_results.jsonl")
    p.add_argument("--output", default="challenger_results/training_readiness.json")
    args = p.parse_args()
    source = Path(args.input)
    rows = [json.loads(x) for x in source.read_text().splitlines() if x.strip()] if source.exists() else []
    report = assess(rows)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
