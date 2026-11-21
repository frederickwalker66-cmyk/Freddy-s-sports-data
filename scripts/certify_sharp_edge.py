"""Fail-closed Sharp Edge certification gate.

A TAKE requires two independently signed attestations: one for the model
probability and one for the exact sportsbook quote. Keys must be held by
different custodians and supplied as environment secrets, never committed.
This gate cannot authenticate Champion-001 by itself.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
import math
import os
import re
from pathlib import Path

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def verify(record, key):
    if not isinstance(record, dict) or not key or len(key) < 32:
        return False
    signature = record.get("signature")
    payload = record.get("payload")
    if not isinstance(signature, str) or len(signature) != 64 or not isinstance(payload, dict):
        return False
    digest = hmac.new(key.encode(), canonical(payload), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, digest)

def parse_time(s):
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else None
    except (ValueError, AttributeError, TypeError):
        return None

def evaluate(candidate, *, model_key=None, odds_key=None, release_key=None, approved_model_versions=(), now=None):
    result = {"decision": "HOLD", "certified": False, "reasons": []}
    reasons = result["reasons"]
    if not isinstance(candidate, dict):
        reasons.append("INVALID_CANDIDATE")
        return result
    model = candidate.get("model_attestation")
    odds = candidate.get("odds_attestation")
    release = candidate.get("release_attestation")
    if not verify(model, model_key):
        reasons.append("MODEL_ATTESTATION_NOT_VERIFIED")
    if not verify(odds, odds_key) or (model_key and odds_key and model_key == odds_key):
        reasons.append("INDEPENDENT_ODDS_ATTESTATION_NOT_VERIFIED")
    if (not verify(release, release_key) or not release_key or
            release_key in (model_key, odds_key)):
        reasons.append("INDEPENDENT_CHAMPION_RELEASE_ATTESTATION_NOT_VERIFIED")
    if reasons:
        return result
    m, o, r = model["payload"], odds["payload"], release["payload"]
    fields = ("event_id", "market_id", "selection_id", "line")
    if any(m.get(f) != o.get(f) or m.get(f) is None for f in fields):
        reasons.append("EXACT_MARKET_MISMATCH")
    p, price = m.get("probability"), o.get("decimal_odds")
    if type(p) not in (float, int) or not math.isfinite(p) or not 0 < p < 1:
        reasons.append("INVALID_MODEL_PROBABILITY")
    if type(price) not in (float, int) or not math.isfinite(price) or not 1 < price <= 1000:
        reasons.append("INVALID_DECIMAL_ODDS")
    if m.get("model_family") != "Champion-001":
        reasons.append("NATIVE_CHAMPION_001_MODEL_REQUIRED")
    sha = re.compile(r"^[0-9a-f]{64}$")
    model_digest = m.get("model_artifact_sha256")
    calibration_digest = m.get("calibration_report_sha256")
    if (not isinstance(model_digest, str) or not sha.fullmatch(model_digest)
            or r.get("model_artifact_sha256") != model_digest
            or not isinstance(calibration_digest, str) or not sha.fullmatch(calibration_digest)
            or r.get("calibration_report_sha256") != calibration_digest
            or r.get("model_version") != m.get("model_version")):
        reasons.append("INDEPENDENT_MODEL_RELEASE_DIGEST_MISMATCH")
    if (r.get("original_champion_001_authenticated") is not True
            or r.get("reference_outputs_independently_reproduced") is not True
            or r.get("calibration_independently_validated") is not True
            or r.get("release_authorized") is not True
            or not isinstance(r.get("release_approval_receipt_id"), str)
            or not r["release_approval_receipt_id"].strip()):
        reasons.append("INDEPENDENT_CHAMPION_PROVENANCE_OR_CALIBRATION_NOT_VERIFIED")
    if not isinstance(m.get("forecast_receipt_id"), str) or not m["forecast_receipt_id"].strip():
        reasons.append("MISSING_NATIVE_FORECAST_RECEIPT")
    if m.get("model_version") is None or m.get("independent_model_validation") is not True:
        reasons.append("MODEL_VALIDATION_NOT_ATTESTED")
    if m.get("model_version") not in approved_model_versions:
        reasons.append("MODEL_RELEASE_NOT_IN_INDEPENDENT_APPROVAL_REGISTRY")
    if o.get("direct_checkout_verified") is not True or not isinstance(o.get("checkout_receipt_id"), str) or not o["checkout_receipt_id"].strip():
        reasons.append("EXECUTABLE_SPORTSBOOK_CHECKOUT_RECEIPT_NOT_VERIFIED")
    if o.get("sportsbook") not in ("DraftKings", "FanDuel"):
        reasons.append("UNSUPPORTED_BOOK")
    now = now or datetime.now(timezone.utc)
    observed, start = parse_time(o.get("observed_at")), parse_time(o.get("event_start"))
    if not observed or not start or not -60 <= (now-observed).total_seconds() <= 120:
        reasons.append("QUOTE_NOT_FRESH")
    if not start or start <= now:
        reasons.append("EVENT_NOT_PREGAME")
    model_time = parse_time(m.get("predicted_at"))
    if not model_time or not observed or model_time > observed or model_time >= start:
        reasons.append("MODEL_PREDICTION_NOT_PREMARKET")
    if reasons:
        return result
    ev = p * price - 1
    result["ev_percent"] = round(ev * 100, 3)
    result["model_probability_percent"] = round(p * 100, 3)
    if ev <= 0:
        result.update(decision="PASS", reasons=["NON_POSITIVE_EXPECTED_VALUE"])
    else:
        result.update(decision="TAKE", certified=True)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="JSON candidate file")
    parser.add_argument("--output", default="validation_output/sharp_edge_certification.json")
    args = parser.parse_args()
    candidate = json.loads(Path(args.input).read_text())
    report = evaluate(candidate, model_key=os.environ.get("SHARP_MODEL_ATTESTATION_KEY"),
                      odds_key=os.environ.get("SHARP_ODDS_ATTESTATION_KEY"),
                      release_key=os.environ.get("SHARP_RELEASE_ATTESTATION_KEY"),
                      approved_model_versions=tuple(x.strip() for x in os.environ.get("SHARP_APPROVED_MODEL_VERSIONS", "").split(",") if x.strip()))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["certified"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
