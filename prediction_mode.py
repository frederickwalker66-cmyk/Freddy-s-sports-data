"""Independent prediction display: never invent a forecast or promote research to certified TAKE."""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


def assess(row, now):
    out = {"event_id": row.get("event_id"), "selection": row.get("selection"),
           "market_type": row.get("market_type"), "model_id": row.get("model_id"),
           "status": "HOLD", "certified": False, "reasons": []}
    reasons = out["reasons"]
    if not row.get("event_id") or not row.get("selection") or not row.get("market_type"):
        reasons.append("MISSING_MARKET_IDENTITY")
    try:
        start = utc(row["event_start_utc"])
        forecast = utc(row["forecast_created_utc"])
        if forecast >= start or now >= start:
            reasons.append("NOT_PREGAME")
        out["event_start_utc"] = start.isoformat()
        out["decision_deadline_utc"] = (start - __import__("datetime").timedelta(minutes=10)).isoformat()
    except (KeyError, TypeError, ValueError):
        reasons.append("INVALID_EVENT_OR_FORECAST_TIME")
    p = row.get("model_probability")
    if type(p) not in (int, float) or not math.isfinite(p) or not 0 < p < 1:
        reasons.append("MISSING_NATIVE_MODEL_PROBABILITY")
    else:
        out["model_probability"] = p
    odds = row.get("odds_american")
    if type(odds) not in (int, float) or not math.isfinite(odds) or abs(odds) < 100:
        reasons.append("MISSING_VALID_ODDS")
    elif "model_probability" in out:
        decimal = 1 + (odds / 100 if odds > 0 else 100 / abs(odds))
        out["odds_american"] = odds
        out["break_even_probability"] = round(1 / decimal, 6)
        out["estimated_ev_percent"] = round(100 * (p * decimal - 1), 3)
    if row.get("model_origin") != "native_executable_receipt":
        reasons.append("NATIVE_MODEL_RECEIPT_NOT_VERIFIED")
    if row.get("roster_and_injury_verified") is not True and row.get("is_player_prop") is True:
        reasons.append("PLAYER_AVAILABILITY_NOT_VERIFIED")
    if row.get("checkout_odds_verified") is not True:
        reasons.append("EXECUTABLE_CHECKOUT_ODDS_NOT_VERIFIED")
    if row.get("independent_certification") is not True:
        reasons.append("INDEPENDENT_CERTIFICATION_MISSING")
    research_blockers = [r for r in reasons if r in (
        "MISSING_MARKET_IDENTITY", "NOT_PREGAME",
        "INVALID_EVENT_OR_FORECAST_TIME", "MISSING_NATIVE_MODEL_PROBABILITY",
        "MISSING_VALID_ODDS", "NATIVE_MODEL_RECEIPT_NOT_VERIFIED",
        "PLAYER_AVAILABILITY_NOT_VERIFIED",
    )]
    out["research_status"] = "RESEARCH_READY" if not research_blockers else "RESEARCH_HOLD"
    out["research_blockers"] = research_blockers
    out["research_lean"] = (
        "POSITIVE_EV_RESEARCH" if out["research_status"] == "RESEARCH_READY"
        and out.get("estimated_ev_percent", 0) > 0 else
        "NON_POSITIVE_EV_RESEARCH" if out["research_status"] == "RESEARCH_READY"
        else "NO_VALID_RESEARCH_SELECTION"
    )
    # Input flags are self-asserted; this display never issues a certified TAKE.
    reasons.append("INDEPENDENT_ATTESTATIONS_NOT_VALIDATED_BY_THIS_WORKFLOW")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="prediction_input/native_forecasts.jsonl")
    parser.add_argument("--output", default="prediction_output/predictions.json")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    source = Path(args.input)
    results = []
    if source.is_file():
        for line in source.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    row = json.loads(line)
                    results.append(assess(row, now))
                except (ValueError, TypeError, AttributeError):
                    results.append({"status": "HOLD", "certified": False, "reasons": ["INVALID_FORECAST_RECORD"]})
    report = {"mode": "prediction", "generated_utc": now.isoformat(),
              "native_forecast_source_present": source.is_file(),
              "forecasts": results, "certified_take_count": 0,
              "research_ready_count": sum(x.get("research_status") == "RESEARCH_READY" for x in results),
              "status": "HOLD", "champion_001_modified": False,
              "note": "Predictions appear only if real native forecast receipts are supplied; this display never self-certifies."}
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"forecasts": len(results), "certified_take_count": 0, "status": "HOLD"}))


if __name__ == "__main__":
    main()
