"""Independent, read-only calibration audit of timestamped Champion-001 forecasts.

Input JSONL records require model_id, prediction timestamp, event start,
model_probability, binary outcome, event_id, selection_id, and immutable
model artifact hash. This audits evidence; it never trains or changes Champion.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def _time(s):
    if not isinstance(s, str):
        raise ValueError("timestamp_required")
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)


def evaluate(records, *, minimum=200, bins=10):
    seen = set()
    valid = []
    rejected = []
    hashes = set()
    for index, row in enumerate(records):
        try:
            if not isinstance(row, dict) or row.get("model_id") != "Champion-001":
                raise ValueError("not_champion_001")
            p = row.get("model_probability")
            y = row.get("outcome")
            if type(p) not in (float, int) or not math.isfinite(p) or not 0 < p < 1:
                raise ValueError("invalid_probability")
            if type(y) is not int or y not in (0, 1):
                raise ValueError("invalid_binary_outcome")
            if _time(row.get("predicted_at")) >= _time(row.get("event_start_at")):
                raise ValueError("not_pregame")
            identity = (row.get("event_id"), row.get("selection_id"))
            if not all(identity) or identity in seen:
                raise ValueError("duplicate_or_missing_identity")
            sha = row.get("model_artifact_sha256")
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdefABCDEF" for c in sha):
                raise ValueError("missing_model_artifact_hash")
            seen.add(identity)
            hashes.add(sha.lower())
            valid.append((float(p), y))
        except (ValueError, TypeError, OverflowError) as exc:
            rejected.append({"index": index, "reason": str(exc)})
    n = len(valid)
    brier = sum((p-y)**2 for p, y in valid)/n if n else None
    log_loss = -sum(y*math.log(p)+(1-y)*math.log1p(-p) for p,y in valid)/n if n else None
    calibration = []
    weighted_gap = 0
    for i in range(bins):
        bucket = [(p,y) for p,y in valid if min(int(p*bins), bins-1)==i]
        if not bucket:
            continue
        avg_p = sum(p for p,_ in bucket)/len(bucket)
        rate = sum(y for _,y in bucket)/len(bucket)
        weighted_gap += len(bucket)*abs(avg_p-rate)
        calibration.append({"bin": i, "count": len(bucket), "mean_probability": avg_p,
                            "observed_frequency": rate})
    ece = weighted_gap/n if n else None
    blockers = []
    if n < minimum:
        blockers.append("insufficient_independent_out_of_sample_examples")
    if rejected:
        blockers.append("invalid_records_present")
    if len(hashes) != 1:
        blockers.append("mixed_or_missing_frozen_model_artifact")
    blockers.extend(["outcomes_and_forecasts_not_independently_authenticated",
                     "no_out_of_sample_split_or_leakage_audit",
                     "no_market_specific_calibration_acceptance_threshold",
                     "no_live_source_or_ev_certification"])
    return {"model_id": "Champion-001", "sample_size": n, "rejected": rejected,
            "brier_score": brier, "log_loss": log_loss, "expected_calibration_error": ece,
            "bins": calibration, "model_hash_count": len(hashes),
            "certification": "HOLD", "certified_take_count": 0, "blockers": blockers}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSONL forecast/outcome audit file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--minimum", type=int, default=200)
    args = parser.parse_args()
    if args.minimum < 1:
        parser.error("minimum must be positive")
    with Path(args.input).open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    result = evaluate(records, minimum=args.minimum)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"sample_size": result["sample_size"], "certification": result["certification"],
                      "output": str(output)}))


if __name__ == "__main__":
    main()
