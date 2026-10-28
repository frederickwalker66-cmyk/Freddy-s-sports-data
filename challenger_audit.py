"""Read-only Challenger-001 intake validation; never generates or places bets.

Without an independently reviewed game schedule ALL observations are quarantined.
Passing these checks permits research staging only; independent sportsbook price verification and independently generated probabilities remain REQUIRED before betting.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from roster_validation import check_player_roster, load_rosters
from availability_validation import check_availability, load_availability


def parse_utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp missing")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return dt.astimezone(timezone.utc)


def load_schedule(path):
    if path is None:
        return {}  # Missing independent schedule: quarantine every record.
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


def market_family(row):
    """Classify recorded source markets; does not certify sportsbook availability."""
    if not isinstance(row, dict):
        return "unknown"
    market = row.get("market_type")
    league = row.get("league")
    if not isinstance(market, str):
        return "unknown"
    if market.startswith("player_"):
        return "player_prop"
    if (market == "point_spread" and league in ("nba", "nfl")) or (market == "run_line" and league == "mlb"):
        return "spread"
    if market == "moneyline":
        return "moneyline"
    if market.startswith("total_"):
        return "total"
    return "other"


def valid_number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def validate(row, events, rosters=None, availability=None):
    rosters = rosters if rosters is not None else {}
    availability = availability if availability is not None else {}
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
        if age < 0 or age > 120:
            reasons.append("quote_too_old_or_future")
        if event is not None:
            independent_start = parse_utc(event["start_utc"])
            if abs((provider_start - independent_start).total_seconds()) > 60:
                reasons.append("event_start_mismatch")
            if source_time >= independent_start or collected_time >= independent_start:
                reasons.append("not_verified_pregame")
    except (TypeError, ValueError, OverflowError):
        reasons.append("invalid_timestamp")
    family = market_family(row)
    if family in ("unknown", "other"):
        reasons.append("unsupported_market_family")
    if family == "spread":
        if row.get("is_player_prop") is not False:
            reasons.append("spread_prop_flag_mismatch")
        if row.get("selection_type") not in ("home", "away"):
            reasons.append("spread_team_side_missing")
        if not valid_number(row.get("line")):
            reasons.append("invalid_spread_line")
    if family == "player_prop" and row.get("is_player_prop") is not True:
        reasons.append("player_market_flag_mismatch")
    if family == "player_prop" and row.get("selection_type") not in ("over", "under", "yes", "no"):
        reasons.append("unsupported_player_prop_side")
    player_prop = row.get("is_player_prop")
    if player_prop is True:
        if not row.get("player_name") or not row.get("player_id"):
            reasons.append("unresolved_player_identity")
        if not row.get("market_type", "").startswith("player_"):
            reasons.append("player_market_mismatch")
        if not valid_number(row.get("line")):
            reasons.append("invalid_player_line")
        reasons.extend(check_player_roster(row, rosters))
        reasons.extend(check_availability(row, availability))
    elif player_prop is not False:
        reasons.append("unknown_prop_class")
    return sorted(set(reasons))


def audit(rows, events, rosters=None, availability=None):
    rosters = rosters if rosters is not None else {}
    availability = availability if availability is not None else {}
    staged, quarantined = [], []
    causes, leagues, families, staged_families, quarantined_families = Counter(), Counter(), Counter(), Counter(), Counter()
    for row in rows:
        reasons = validate(row, events, rosters, availability)
        leagues[row.get("league", "unknown") if isinstance(row, dict) else "unknown"] += 1
        causes.update(reasons)
        family = market_family(row)
        families[family] += 1
        if reasons:
            quarantined.append({"observation": row, "reasons": reasons})
            quarantined_families[family] += 1
        else:
            staged.append(row)
            staged_families[family] += 1
    summary = {
        "mode": "challenger_001_research_only",
        "observations": len(rows),
        "max_research_quote_age_seconds": 120,
        "independent_schedule_events_available": len(events),
        "independently_reviewed_roster_entries_available": len(rosters),
        "roster_refresh_automated": False,
        "max_roster_age_seconds": 86400,
        "independently_reviewed_game_day_status_entries": len(availability),
        "game_day_status_sync_automated": False,
        "max_game_day_status_age_seconds": 7200,
        "staged_for_research_only": len(staged),
        "quarantined": len(quarantined),
        "quarantine_causes": dict(sorted(causes.items())),
        "by_league": dict(sorted(leagues.items())),
        "observed_market_families": dict(sorted(families.items())),
        "staged_research_market_families": dict(sorted(staged_families.items())),
        "quarantined_market_families": dict(sorted(quarantined_families.items())),
        "collected_player_prop_observations": families["player_prop"],
        "collected_spread_and_run_line_observations": families["spread"],
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
    p.add_argument("--schedule", default=None, help="Independently reviewed event schedule manifest; if absent, all observations are quarantined")
    p.add_argument("--rosters", default=None, help="Externally reviewed official roster and provider-ID manifest; no manifest quarantines all player props")
    p.add_argument("--availability", default=None, help="Externally verified game-day injury and lineup status manifest; absent means player props quarantined")
    p.add_argument("--output-dir", default="research_output")
    args = p.parse_args(argv)
    events = load_schedule(args.schedule)
    rosters = load_rosters(args.rosters)
    availability = load_availability(args.availability)
    with Path(args.input).open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    staged, quarantined, report = audit(rows, events, rosters, availability)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "research_only.jsonl", staged)
    write_jsonl(out / "quarantine.jsonl", quarantined)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
