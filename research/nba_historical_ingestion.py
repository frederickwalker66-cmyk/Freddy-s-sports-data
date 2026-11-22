"""Stage externally collected NBA historical records without inventing as-of proof.

Input: JSONL archived candidate records with real provenance. Never auto-attest.
"""
import argparse
import json
from pathlib import Path
from challenger_backtest import validate_record
from challenger_nba_probability import qualified_history

def ingest(source, output, report_path):
    rows, qualified, review, rejected, seen = 0, [], [], [], set()
    if source.is_file():
        for number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            rows += 1
            try:
                item = json.loads(line)
                validate_record(item)
                if item["league"] != "nba" or item["selection_type"] != "home":
                    raise ValueError("only NBA home moneyline records supported")
                if item["event_id"] in seen:
                    raise ValueError("duplicate event_id")
                seen.add(item["event_id"])
                try:
                    qualified_history(item)
                    qualified.append(item)
                except ValueError:
                    review.append({"line": number, "event_id": item["event_id"],
                                   "reason": "requires_independent_asof_outcome_review_and_snapshot_hashes"})
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                rejected.append({"line": number, "reason": str(exc)[:160]})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(x, sort_keys=True)+"\\n" for x in qualified), encoding="utf-8")
    report = {"source_exists": source.is_file(), "rows_received": rows,
              "review_attested_rows": len(qualified), "awaiting_review": review[:100],
              "rejected": rejected[:100], "minimum_required": 250,
              "attestations_are_not_independent_proof": True,
              "certified_takes": 0, "champion_001_modified": False,
              "next_action": "Supply authentic archived pregame snapshots and independently review their provenance" if len(qualified)<250 else "Run training with separate source authenticity review"}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True)+"\\n", encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("source_exists","rows_received","review_attested_rows","minimum_required")}))
    return report

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--source", default="prediction_input/nba_historical_candidates.jsonl")
    p.add_argument("--output", default="prediction_input/qualified_nba_history.jsonl")
    p.add_argument("--report", default="challenger_results/nba_probability/ingestion_report.json")
    args=p.parse_args()
    ingest(Path(args.source), Path(args.output), Path(args.report))
