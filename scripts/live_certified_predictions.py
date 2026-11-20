"""Run the live Sharp Edge certification gate on a bounded candidate batch.

No fabricated picks: empty/missing inputs produce zero TAKE selections.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from scripts.certify_sharp_edge import evaluate

def run(candidates, *, model_key=None, odds_key=None, approved_model_versions=(), now=None):
    if not isinstance(candidates, list) or len(candidates) > 500:
        raise ValueError("expected at most 500 candidates")
    now = now or datetime.now(timezone.utc)
    rows = []
    for index, candidate in enumerate(candidates):
        verdict = evaluate(candidate, model_key=model_key, odds_key=odds_key, approved_model_versions=approved_model_versions, now=now)
        # The raw candidate and secret signatures are never copied to public output.
        row = {"index": index + 1, **verdict}
        if verdict["certified"]:
            payload = candidate["odds_attestation"]["payload"]
            for field in ("event_id", "market_id", "selection_id", "line", "sportsbook", "decimal_odds", "event_start"):
                if isinstance(payload.get(field), (str, int, float)) and not isinstance(payload.get(field), bool):
                    row[field] = payload[field]
        rows.append(row)
    rows.sort(key=lambda row: (row["decision"] != "TAKE", -row.get("ev_percent", -999999), row["index"]))
    return {
        "generated_at_utc": now.isoformat(),
        "mode": "LIVE_CERTIFICATION_GATE",
        "certified_take_count": sum(x["decision"] == "TAKE" for x in rows),
        "pass_count": sum(x["decision"] == "PASS" for x in rows),
        "hold_count": sum(x["decision"] == "HOLD" for x in rows),
        "decisions": rows,
        "no_certified_picks": not any(x["decision"] == "TAKE" for x in rows),
        "best_bets": [x for x in rows if x["decision"] == "TAKE"][:10],
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="certification_input/candidates.json")
    p.add_argument("--output", default="validation_output/live_certified_predictions.json")
    args = p.parse_args()
    path = Path(args.input)
    if path.is_file():
        try:
            candidates = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            raise SystemExit("Invalid candidate JSON; no certified predictions")
    else:
        candidates = []
    report = run(candidates, model_key=os.getenv("SHARP_MODEL_ATTESTATION_KEY"),
                 odds_key=os.getenv("SHARP_ODDS_ATTESTATION_KEY"),
                 approved_model_versions=tuple(v.strip() for v in os.getenv("SHARP_APPROVED_MODEL_VERSIONS", "").split(",") if v.strip()))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "decisions"}))

if __name__ == "__main__":
    main()
