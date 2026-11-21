"""Validate provenance metadata before admitting historical records to Challenger-002.

Research-only. No credentials, API calls, training, or Certified TAKE.
This cannot independently authenticate upstream provider claims.
"""
import argparse
import hashlib
import json
from pathlib import Path
from research.challenger_002_baseline import timestamp

REQUIRED = ("event_id", "event_start_at", "observed_at", "outcome_observed_at",
            "outcome", "features", "source_provider", "source_record_id",
            "source_observed_at", "source_payload_sha256", "league", "market")

def inspect(rows):
    errors, accepted, seen = [], 0, set()
    for i, row in enumerate(rows):
        try:
            if not isinstance(row, dict):
                raise ValueError("not_object")
            for k in REQUIRED:
                if k not in row:
                    raise ValueError("missing_" + k)
            for k in ("event_id", "source_provider", "source_record_id", "league", "market"):
                if not isinstance(row[k], str) or not row[k].strip():
                    raise ValueError("invalid_" + k)
            if row["source_provider"] != "SportsDataIO":
                raise ValueError("unexpected_provider")
            sha = row["source_payload_sha256"]
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("invalid_source_sha256")
            start, observed = timestamp(row["event_start_at"]), timestamp(row["observed_at"])
            sourced, outcome_time = timestamp(row["source_observed_at"]), timestamp(row["outcome_observed_at"])
            if not (sourced <= observed < start < outcome_time):
                raise ValueError("invalid_point_in_time_order")
            if type(row["outcome"]) is not int or row["outcome"] not in (0, 1):
                raise ValueError("invalid_outcome")
            features = row["features"]
            if not isinstance(features, dict) or not features or any(
                not isinstance(k, str) or not k or type(v) not in (int, float)
                or not __import__("math").isfinite(v) for k,v in features.items()
            ):
                raise ValueError("invalid_features")
            identity = (row["league"], row["market"], row["event_id"])
            if identity in seen:
                raise ValueError("duplicate_market_event")
            seen.add(identity)
            accepted += 1
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append({"row": i, "reason": str(exc)})
    return {"status": "SCHEMA_VALID_ONLY_NOT_SOURCE_AUTHENTICATED" if accepted and not errors else "BLOCKED",
            "accepted": accepted, "rejected": errors,
            "certified_take_count": 0,
            "provenance_independently_verified": False,
            "note": "Hashes and provider names are assertions until checked against independently retained raw responses."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    report = inspect(rows)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
    if report["status"] == "BLOCKED":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
