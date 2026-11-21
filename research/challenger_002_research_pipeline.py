"""Research-only admission gate: validate retained raw receipts before fitting.

A locally matching receipt is NOT proof of provider authentication or of
point-in-time capture. This command cannot certify betting predictions.
"""
import argparse
import json
from pathlib import Path
from research.challenger_002_receipt_verification import verify
from research.challenger_002_baseline import evaluate

def run(rows, receipt_directory, league, market):
    receipt_report = verify(rows, receipt_directory)
    output = {
        "model_id": "Challenger-002", "league": league, "market": market,
        "receipt_validation": receipt_report, "certified_take_count": 0,
        "status": "BLOCKED", "research_only": True
    }
    if receipt_report["status"] != "LOCAL_DIGESTS_MATCH_NOT_AUTHENTICATED":
        output["blockers"] = ["RAW_RECEIPT_VALIDATION_FAILED"]
        return output
    if any(row.get("league") != league or row.get("market") != market for row in rows):
        output["blockers"] = ["MIXED_LEAGUE_OR_MARKET"]
        return output
    report = evaluate(rows)
    output["evaluation"] = report
    output["status"] = report["status"]
    output["blockers"] = report.get("blockers", [])
    if "PROVIDER_AUTHENTICATION_AND_CUSTODY_REQUIRED" not in output["blockers"]:
        output["blockers"].append("PROVIDER_AUTHENTICATION_AND_CUSTODY_REQUIRED")
    return output

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--receipts", required=True)
    p.add_argument("--league", required=True)
    p.add_argument("--market", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    rows = [json.loads(s) for s in Path(args.input).read_text().splitlines() if s.strip()]
    result = run(rows, args.receipts, args.league, args.market)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))
    if result["status"] == "BLOCKED":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
