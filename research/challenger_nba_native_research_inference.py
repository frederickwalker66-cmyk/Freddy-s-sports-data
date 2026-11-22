"""Run existing trained Challenger NBA home-moneyline artifact, research only."""
import argparse
import json
from pathlib import Path
from challenger_nba_probability import VERSION, digest, predict_probability

def infer(model, event):
    if not isinstance(model, dict) or model.get("version") != VERSION or model.get("lane") != "Challenger-001":
        raise ValueError("wrong_model_identity")
    if model.get("market_type") != "nba_home_moneyline" or model.get("status") != "unverified_research_model_not_deployed":
        raise ValueError("wrong_model_market_or_status")
    if model.get("champion_001_modified") is not False or model.get("qualified_for_real_money_wagers") is not False:
        raise ValueError("model_safety_flags_invalid")
    original = dict(model)
    recorded = original.pop("artifact_sha256", None)
    if not isinstance(recorded, str) or digest(original) != recorded:
        raise ValueError("model_artifact_integrity_failed")
    if model.get("holdout_excluded_from_coefficients") is not True:
        raise ValueError("holdout_contamination_risk")
    if not isinstance(event, dict) or not isinstance(event.get("event_id"), str) or not event["event_id"].strip() or not isinstance(event.get("home_team"), str) or not event["home_team"].strip() or not isinstance(event.get("away_team"), str) or not event["away_team"].strip() or event["home_team"] == event["away_team"]:
        raise ValueError("event_identity_missing")
    if event.get("pregame_source_verified") is not True or not event.get("features_asof_utc") or not event.get("event_start_utc") or event.get("league") != "nba":
        raise ValueError("pregame_evidence_missing")
    from datetime import datetime, timezone
    def when(s):
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None: raise ValueError("timezone_missing")
        return d.astimezone(timezone.utc)
    if not when(event["features_asof_utc"]) < datetime.now(timezone.utc) < when(event["event_start_utc"]):
        raise ValueError("not_valid_pregame")
    p = predict_probability(model["fit"], event.get("features"))
    return {"event_id": event["event_id"], "home_team": event["home_team"],
            "away_team": event["away_team"], "model_id": "Challenger-001",
            "market": "nba_home_moneyline", "home_win_probability": p,
            "away_win_probability": 1-p, "model_artifact_sha256": recorded,
            "status": "UNCERTIFIED_RESEARCH_ONLY", "certified": False,
            "take": False, "champion_001_modified": False}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    model = json.loads(Path(args.model).read_text())
    event = json.loads(Path(args.event).read_text())
    report = infer(model, event)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")

if __name__ == "__main__":
    main()
