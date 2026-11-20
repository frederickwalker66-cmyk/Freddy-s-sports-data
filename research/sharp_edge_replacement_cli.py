"""Offline CLI adapter for the existing Sharp Edge TAKE-only replacement engine.

Reads an explicitly supplied JSON snapshot, never fetches live odds or bets.
Example: python -m research.sharp_edge_replacement_cli --input snapshot.json --output report.json
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

from research.sharp_edge_replacements import Candidate, evaluate, replace_passes


def parse_datetime(value):
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def candidate_from_json(item):
    required = ("selection_id", "market", "american_odds", "model_probability",
                "model_id", "model_verified", "odds_verified", "odds_timestamp",
                "evaluation_timestamp", "injury_verified", "matchup_verified",
                "minutes_verified", "calibrated")
    missing = [key for key in required if key not in item]
    if missing:
        raise ValueError("Missing required candidate fields: " + ", ".join(missing))
    for flag in ("model_verified", "odds_verified", "injury_verified",
                 "matchup_verified", "minutes_verified", "calibrated"):
        if type(item[flag]) is not bool:
            raise ValueError(flag + " must be a JSON boolean")
    if item.get("game_started", False) not in (True, False) or type(item.get("game_started", False)) is not bool:
        raise ValueError("game_started must be a JSON boolean")
    if type(item["american_odds"]) is not int:
        raise ValueError("american_odds must be an integer")
    if item["model_probability"] is not None and type(item["model_probability"]) not in (float, int):
        raise ValueError("model_probability must be a number or null")
    return Candidate(**{**{k: item[k] for k in required},
                        "odds_timestamp": parse_datetime(item["odds_timestamp"]),
                        "evaluation_timestamp": parse_datetime(item["evaluation_timestamp"]),
                        **{k: item[k] for k in ("game_started", "correlation_group", "confidence_grade") if k in item}})


def run(snapshot):
    if not isinstance(snapshot.get("original"), list) or not isinstance(snapshot.get("candidates"), list):
        raise ValueError("Snapshot requires original and candidates arrays")
    original = snapshot["original"]
    if len(original) > 8:
        raise ValueError("At most eight original legs supported")
    if any(not isinstance(x, dict) or "selection_id" not in x or "decision" not in x for x in original):
        raise ValueError("Each original leg needs selection_id and decision")
    candidates = [candidate_from_json(item) for item in snapshot["candidates"]]
    result = replace_passes(original, candidates)
    result["candidate_audit"] = [evaluate(c) for c in candidates]
    result["source_status"] = "SUPPLIED_SNAPSHOT_ONLY_NOT_LIVE_VERIFIED"
    result["certification_note"] = ("Input verification flags are assertions from the supplied snapshot; "
                                    "this adapter does not independently authenticate model, sportsbook, or injury data.")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = run(snapshot)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["betting_status"],
                      "replacements": len([r for r in result["replacements"] if r["decision"] == "TAKE"]),
                      "output": args.output}))


if __name__ == "__main__":
    main()
