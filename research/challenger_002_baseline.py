"""Challenger-002: isolated, research-only logistic baseline.

No sportsbook API, no certified TAKE output, no Champion-001 modification.
Input JSONL rows: event_id, event_start_at, observed_at, features (numeric
mapping), outcome (0 or 1). Only use features known at observed_at.
Chronological train/test split; the test portion is never used to fit.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

MODEL_ID = "Challenger-002"

def timestamp(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone_required")
    return dt.astimezone(timezone.utc)

def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, z))))

def evaluate(rows, train_fraction=0.7, min_train=200, min_test=50):
    if not 0 < train_fraction < 1:
        raise ValueError("invalid_split")
    valid, rejected, seen = [], [], set()
    for i, row in enumerate(rows):
        try:
            event_id = row["event_id"]
            if not isinstance(event_id, str) or not event_id or event_id in seen:
                raise ValueError("missing_or_duplicate_event")
            start, observed = timestamp(row["event_start_at"]), timestamp(row["observed_at"])
            if observed >= start:
                raise ValueError("not_pregame")
            outcome = row["outcome"]
            if type(outcome) is not int or outcome not in (0, 1):
                raise ValueError("invalid_outcome")
            features = row["features"]
            if not isinstance(features, dict) or not features:
                raise ValueError("missing_features")
            if any(not isinstance(k, str) or not k or type(v) not in (int, float)
                   or not math.isfinite(v) for k, v in features.items()):
                raise ValueError("invalid_features")
            seen.add(event_id)
            valid.append((start, observed, event_id, features, outcome))
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            rejected.append({"row": i, "reason": str(exc)})
    valid.sort(key=lambda r: (r[0], r[2]))
    split = int(len(valid) * train_fraction)
    train, test = valid[:split], valid[split:]
    report = {"model_id": MODEL_ID, "status": "BLOCKED", "valid_rows": len(valid),
              "rejected_rows": rejected, "train_rows": len(train), "test_rows": len(test),
              "certified_take_count": 0, "research_only": True}
    if len(train) < min_train or len(test) < min_test:
        report["blockers"] = ["INSUFFICIENT_POINT_IN_TIME_DATA"]
        return report
    # No training on future events or features observed after first test kickoff.
    cutoff = test[0][0]
    if any(r[1] >= cutoff for r in train):
        report["blockers"] = ["TRAIN_FEATURES_OVERLAP_TEST_PERIOD"]
        return report
    keys = sorted(set().union(*(r[3].keys() for r in train)))
    if any(set(r[3]) != set(keys) for r in train + test):
        report["blockers"] = ["FEATURE_SCHEMA_MISMATCH"]
        return report
    means = [sum(r[3][k] for r in train) / len(train) for k in keys]
    scales = [max(1e-9, (sum((r[3][k]-m)**2 for r in train) / len(train))**0.5)
              for k, m in zip(keys, means)]
    def x(row):
        return [1.0] + [(row[3][k]-m)/s for k,m,s in zip(keys,means,scales)]
    weights = [0.0] * (len(keys)+1)
    for _ in range(500):
        grad = [0.0] * len(weights)
        for row in train:
            vec = x(row)
            error = sigmoid(sum(w*v for w,v in zip(weights,vec))) - row[4]
            for j,v in enumerate(vec):
                grad[j] += error*v
        for j in range(len(weights)):
            weights[j] -= 0.05*(grad[j]/len(train) + (0.001*weights[j] if j else 0))
    predictions = [sigmoid(sum(w*v for w,v in zip(weights,x(r)))) for r in test]
    brier = sum((p-r[4])**2 for p,r in zip(predictions,test))/len(test)
    logloss = -sum(r[4]*math.log(max(1e-12,p))+(1-r[4])*math.log(max(1e-12,1-p))
                   for p,r in zip(predictions,test))/len(test)
    report.update(status="RESEARCH_EVALUATED_NOT_CERTIFIED", test_brier=round(brier,6),
                  test_log_loss=round(logloss,6), feature_names=keys,
                  blockers=["INDEPENDENT_PROVENANCE_AUDIT_REQUIRED",
                            "MARKET_SPECIFIC_CALIBRATION_REQUIRED",
                            "SIGNED_ODDS_AND_RELEASE_EVIDENCE_REQUIRED"])
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    result = evaluate(rows)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
