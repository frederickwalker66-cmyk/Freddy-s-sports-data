"""Read-only Challenger-001 intake validation; never generates or places bets.

An independently sourced, reviewed event schedule manifest is REQUIRED.
Passing these checks permits research staging, not tradable odds or predictions.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path


def parse_utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp missing")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return dt.astimezone(timezone.utc)


def load_schedule(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data.get("events"), list):
        raise ValueError("schedule.events must be a list")
    events = {}
    for row in data["events"]:
        if not isinstance(row, dict) or not all(row.get(k) for k in
            ("event_id", "league", "home_team", "away_team", "start_utc", "source_url")):
            raise ValueError("incomplete independently sourced event manifest")
        if row["event_id"] in events:
            raise ValueError("duplicate event id in schedule")
        parse_utc(row["start_utc"])
        events[row["event_id"]] = row
    return events


def validate(row, events):
    reasons = []
    if not isinstance(row, dict):
        return ["invalid_record"]
    if row.get("sportsbook") != "draftkings":
        reasons.append("non_draftkings")
    if row.get("record_type") != "pregame_odds_observation":
        reasons.append("bad_record_type")
    if row.get("certified_prediction") is not False or row.get("model_probability") is not None:
        reasons.append("unexpected_prediction_field")
    if not row.get("event_id") or not row.get("market_type") or not row.get("selection"):
        reasons.append("missing_market_identity")
    if row.get("is_main_line") is not True or row.get("is_alternate_line") is not False:
        reasons.append("not_confirmed_primary_line")
    odds = row.get("odds_american")
    if isinstance(odds, bool) or not isinstance(odds, (int, float)) or not math.isfinite(odds) or abs(odds) < 100:
        reasons.append("invalid_american_odds")
    else:
        expected = 1 + (odds / 100 if odds > 0 else 100 / abs(odds))
        decimal = row.get("odds_decimal")
        if isinstance(decimal, bool) or not isinstance(decimal, (int, float)) or not math.isfinite(decimal) or abs(decimal - expected) > 0.025:
            reasons.append("inconsistent_decimal_odds")
    event = events.get(row.get("event_id"))
    if event is None:
        reasons.append("independent_schedule_unknown")
    elif any(row.get(k) != event[k] for k in ("league", "home_team", "away_team")):
        reasons.append("event_identity_mismatch")
    try:
        source_time = parse_utc(row.get("timestamp"))
        collected_time = parse_utc(row.get("recorded_at"))
        provider_start = parse_utc(row.get("event_start_time"))
        age = (collected_time - source_time).total_seconds()
        if age < 0 or age > 900:
            reasons.append("quote_too_old_or_future")
        if event is not None:
            independent_start = parse_utc(event["start_utc"])
            if abs((provider_start - independent_start).total_seconds()) > 60:
                reasons.append("event_start_mismatch")
            if source_time >= independent_start or collected_time >= independent_start:
                reasons.append("not_verified_pregame")
    except (TypeError, ValueError, OverflowError):
        reasons.append("invalid_timestamp")
    player_prop = row.get("is_player_prop")
    if player_prop is True:
        if not row.get("player_name") or not row.get("player_id"):
            reasons.append("unresolved_player_identity")
        if not row.get("market_type", "").startswith("player_"):
            reasons.append("player_market_mismatch")
        if isinstance(row.get("line"), bool) or not isinstance(row.get("line"), (int, float)):
            reasons.append("invalid_player_line")
    elif player_prop is not False:
        reasons.append("unknown_prop_class")
    return sorted(set(reasons))


def audit(rows, events):
    staged, quarantined = [], []
    causes, leagues = Counter(), Counter()
    for row in rows:
        reasons = validate(row, events)
        leagues[row.get("league", "unknown") if isinstance(row, dict) else "unknown"] += 1
        causes.update(reasons)
        if reasons:
            quarantined.append({"observation": row, "reasons": reasons})
        else:
            staged.append(row)
    summary = {
        "mode": "challenger_001_research_only",
        "observations": len(rows),
        "staged_for_research_only": len(staged),
        "quarantined": len(quarantined),
        "quarantine_causes": dict(sorted(causes.items())),
        "by_league": dict(sorted(leagues.items())),
        "independently_reverified_sportsbook_prices": 0,
        "certified_challenger_predictions": 0,
        "certified_champion_001_predictions": 0,
        "bet_ready_selections": 0,
        "automated_bets_placed": 0,
        "champion_001_modified": False,
        "warning": "Research staging is NOT sportsbook verification, a model forecast, or permission to bet."
    }
    return staged, quarantined, summary


def write_jsonl(path, records):
    with Path(path).open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="SharpAPI JSONL snapshot")
    p.add_argument("--schedule", required=True, help="Independently reviewed event schedule manifest")
    p.add_argument("--output-dir", default="research_output")
    args = p.parse_args(argv)
    events = load_schedule(args.schedule)
    with Path(args.input).open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    staged, quarantined, report = audit(rows, events)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "research_only.jsonl", staged)
    write_jsonl(out / "quarantine.jsonl", quarantined)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
