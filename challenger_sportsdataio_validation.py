"""Validate SportsDataIO score receipts as quarantined Challenger evidence.

Postgame API retrieval never proves pregame availability, historical odds,
official settlement, or permission to train. No model is imported or changed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

LEAGUES = frozenset(("nba", "nfl", "mlb", "nhl", "ncaaf", "ncaab"))
FORBIDDEN = ("qualified_for_challenger_backtest", "certified_prediction",
             "champion_001_modified")


def validate_file(path):
    counts = Counter()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("non-object record")
            if record.get("source") != "sportsdataio" or record.get("league") not in LEAGUES:
                raise ValueError("invalid provider or unsupported league")
            if not isinstance(record.get("provider_payload"), dict):
                raise ValueError("missing raw provider payload")
            if any(record.get(k) is not False for k in FORBIDDEN):
                raise ValueError("unsafe promotion flag")
            started = datetime.fromisoformat(record["request_started_utc"].replace("Z", "+00:00"))
            received = datetime.fromisoformat(record["received_at_utc"].replace("Z", "+00:00"))
            if (started.tzinfo is None or received.tzinfo is None or
                    received < started or received > datetime.now(timezone.utc)):
                raise ValueError("invalid retrieval timestamps")
            if not isinstance(record.get("requested_date_utc"), str):
                raise ValueError("missing requested date")
            counts[record["league"]] += 1
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"{Path(path).name} line {number}: {exc}") from exc
    return counts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", required=True)
    p.add_argument("--output-dir", default="sportsdataio_validation")
    args = p.parse_args()
    root = Path(args.input_dir)
    files = sorted(root.glob("*.jsonl"))
    if not files:
        raise SystemExit("No SportsDataIO JSONL evidence files found")
    totals = Counter()
    for path in files:
        totals.update(validate_file(path))
    report = {
        "stage": "challenger_sportsdataio_quarantined_evidence_validation",
        "source": "sportsdataio",
        "files_checked": len(files),
        "records_validated": sum(totals.values()),
        "by_league": dict(sorted(totals.items())),
        "independently_verified_pregame_features": 0,
        "independently_verified_historical_odds": 0,
        "qualified_training_examples": 0,
        "certified_predictions": 0,
        "bet_ready_selections": 0,
        "champion_001_modified": False,
        "warning": "Postgame receipts are research evidence only; no training or prediction promotion.",
    }
    dest = Path(args.output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
