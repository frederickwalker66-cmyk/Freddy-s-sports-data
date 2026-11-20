"""Source readiness audit for Sharp Edge; read-only and fail-closed.

This module does not access GitHub secrets, sportsbook APIs or model weights.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _time(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (AttributeError, ValueError, TypeError):
        return None


def audit(snapshot, now=None):
    now = now or datetime.now(timezone.utc)
    rows = snapshot.get("markets", [])
    if not isinstance(rows, list):
        raise ValueError("markets must be a list")
    results = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each market must be an object")
        issues = []
        if not row.get("source") or not row.get("source_record_id"):
            issues.append("missing_source_identity")
        observed = _time(row.get("observed_at"))
        if observed is None or not 0 <= (now - observed).total_seconds() <= 900:
            issues.append("unverified_or_stale_observation")
        if not row.get("event_id") or not row.get("market") or not row.get("selection_id"):
            issues.append("missing_market_identity")
        if not row.get("sportsbook"):
            issues.append("missing_sportsbook")
        if type(row.get("american_odds")) is not int or abs(row["american_odds"]) < 100:
            issues.append("invalid_odds")
        if row.get("champion_model_id") != "Champion-001" or not row.get("champion_forecast_receipt"):
            issues.append("missing_native_champion_receipt")
        if not row.get("independent_verification_receipt"):
            issues.append("missing_independent_verification")
        # Even apparently complete user-supplied receipts are not authenticated here.
        issues.append("source_receipts_not_cryptographically_authenticated")
        results.append({"selection_id": row.get("selection_id"), "decision": "HOLD",
                        "issues": issues})
    return {"status": "HOLD_UNTIL_AUTHENTICATED_SOURCE_AND_MODEL_EVIDENCE",
            "rows_examined": len(results), "certified_takes": 0,
            "markets": results, "read_only": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = audit(snapshot)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "rows_examined": result["rows_examined"]}))


if __name__ == "__main__":
    main()
