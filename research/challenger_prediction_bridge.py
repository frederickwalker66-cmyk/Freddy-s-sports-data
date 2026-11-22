"""Bridge genuine Challenger NBA model output into the existing prediction display.

Requires an actual trained model and future candidate. No synthetic fallback.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from challenger_nba_probability import score_future_event
from prediction_mode import assess

def bridge(model, candidate, now=None):
    now = now or datetime.now(timezone.utc)
    projection = score_future_event(model, candidate, now=now)
    row = {
        "event_id": candidate["event_id"],
        "selection": "home",
        "market_type": "moneyline",
        "model_id": projection["model_version"],
        "event_start_utc": candidate["start_utc"],
        "forecast_created_utc": projection["scored_at_utc"],
        "model_probability": projection["research_probability_home_win"],
        "model_origin": "native_executable_receipt",
        "odds_american": candidate.get("odds_american"),
        "checkout_odds_verified": False,
        "independent_certification": False,
        "is_player_prop": False,
    }
    result = assess(row, now)
    # A research projection is not evidence of independent feed verification.
    # Preserve explicit gate states so downstream dashboards can identify
    # missing inputs without inferring TAKE eligibility from model probability.
    evidence = candidate.get("verification_evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    required = (
        "event_identity_verified",
        "roster_and_injury_verified",
        "exact_draftkings_market_verified",
        "odds_timestamp_verified",
        "independent_source_verified",
        "model_calibration_verified",
        "independent_certification_verified",
    )
    result["evidence_gates"] = {key: evidence.get(key) is True for key in required}
    result["evidence_blockers"] = [
        key for key, verified in result["evidence_gates"].items() if not verified
    ]
    result["evidence_manifest_complete"] = not result["evidence_blockers"]
    # Even a fully populated caller-provided manifest is NOT an independent
    # attestation; this bridge never releases production predictions.
    result["research_only"] = True
    result["native_model_sha256"] = projection["model_sha256"]
    result["independent_source_provenance_verified"] = False
    result["status"] = "HOLD"
    result["certified"] = False
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    model = json.loads(Path(args.model).read_text())
    candidate = json.loads(Path(args.candidate).read_text())
    result = bridge(model, candidate)
    output = {"status": "HOLD", "certified_take_count": 0,
              "champion_001_modified": False, "forecasts": [result]}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"forecast_count": 1, "certified_take_count": 0, "status": "HOLD"}))
if __name__ == "__main__":
    main()
