"""Capture prospective SportsDataIO NBA feed receipts without exposing licensed payloads.

Run before tipoff. A CI receipt proves retrieval time only; it does not prove
market identity, roster correctness, or independent provider publication time.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from research.sportsdataio_nba_probe import BASE, ENDPOINTS, HOST
from research.trusted_provider_gateway import fetch_provider_json, SourceUnavailable

def capture(day, env=None, fetch=fetch_provider_json):
    env = os.environ if env is None else env
    receipts = {}
    for name, path in ENDPOINTS.items():
        secret = ("SPORTSDATAIO_ODDS_API_KEY" if name in ("pregame_odds", "betting_events")
                  else "SPORTSDATAIO_NBA_API_KEY")
        key = env.get(secret) or env.get("SPORTSDATAIO")
        if not key:
            receipts[name] = {"status": "HOLD_KEY_MISSING"}
            continue
        try:
            response = fetch(BASE + path.replace("{date}", day), api_key=key, allowed_host=HOST)
            payload = response["payload"]
            if not isinstance(payload, list):
                receipts[name] = {"status": "HOLD_SCHEMA_UNEXPECTED"}
                continue
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            receipts[name] = {"status": "CAPTURED_UNVERIFIED", "retrieved_at_utc": response["retrieved_at"],
                              "record_count": len(payload), "canonical_payload_sha256": digest,
                              "transport_authenticated": True, "provider_signature_verified": False,
                              "original_pregame_publication_verified": False}
        except (SourceUnavailable, ValueError, TypeError):
            receipts[name] = {"status": "HOLD_FETCH_FAILED"}
    return {"stage": "prospective_nba_capture", "date": day,
            "receipt_created_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoints": receipts, "raw_provider_records_persisted": False,
            "training_eligible_records": 0, "certified_take_count": 0,
            "champion_001_modified": False,
            "warning": "Receipt-only capture: hashes do not preserve features needed for training. Independent as-of, roster, market and outcome review remains required."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", default="nba_prospective_capture_receipt.json")
    args = parser.parse_args()
    from datetime import date
    if date.fromisoformat(args.date).isoformat() != args.date:
        raise ValueError("invalid date")
    result = capture(args.date)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"statuses": {k: v["status"] for k,v in result["endpoints"].items()},
                      "training_eligible_records": 0, "certified_take_count": 0}))

if __name__ == "__main__":
    main()
