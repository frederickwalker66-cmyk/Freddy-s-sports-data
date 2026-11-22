"""Run existing trained Challenger NBA home-moneyline artifact, research only."""
import argparse
import json
from pathlib import Path
from challenger_nba_probability import VERSION, digest, predict_probability

def infer(model, event):
    """Use the existing prospective scoring gate; never bypass its source checks."""
    from challenger_nba_probability import score_future_event
    result = score_future_event(model, event)
    return {**result, "status": "UNCERTIFIED_RESEARCH_ONLY", "certified": False,
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
