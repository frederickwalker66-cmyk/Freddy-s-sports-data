"""Fail-closed validation for point-in-time player prop observations.

Input: JSON object with observations array. Each record must contain
player_id, team_id, event_id, observed_at, starts_at, roster_verified_at,
injury_verified_at, roster_team_id, status, sportsbook, market, line, odds.
Provider adapters must supply these from authenticated sources.
"""
import datetime as dt
import json
import sys

MAX_ROSTER_AGE_HOURS = 24
MAX_INJURY_AGE_HOURS = 6
MAX_ODDS_AGE_MINUTES = 5

def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.astimezone(dt.timezone.utc)

def validate(record, now):
    reasons = []
    required = ("player_id", "team_id", "event_id", "roster_team_id",
                "sportsbook", "market", "line", "odds", "status")
    for field in required:
        if record.get(field) is None or record.get(field) == "":
            reasons.append("missing_" + field)
    if record.get("team_id") != record.get("roster_team_id"):
        reasons.append("roster_team_mismatch")
    if record.get("status") not in ("active", "available", "confirmed"):
        reasons.append("unverified_or_unavailable_player")
    try:
        observed = parse_time(record.get("observed_at"))
        roster = parse_time(record.get("roster_verified_at"))
        injury = parse_time(record.get("injury_verified_at"))
        start = parse_time(record.get("starts_at"))
        if observed > now or roster > now or injury > now:
            reasons.append("future_timestamp")
        if (now - observed).total_seconds() > MAX_ODDS_AGE_MINUTES * 60:
            reasons.append("stale_odds")
        if (now - roster).total_seconds() > MAX_ROSTER_AGE_HOURS * 3600:
            reasons.append("stale_roster")
        if (now - injury).total_seconds() > MAX_INJURY_AGE_HOURS * 3600:
            reasons.append("stale_injury")
        if start <= now:
            reasons.append("event_already_started")
        if roster > observed or injury > observed:
            reasons.append("verification_after_odds_capture")
    except (ValueError, TypeError, OverflowError):
        reasons.append("invalid_timestamp")
    return sorted(set(reasons))

def main():
    data = json.load(sys.stdin)
    now = dt.datetime.now(dt.timezone.utc)
    accepted, quarantined = [], []
    for record in data.get("observations", []):
        reasons = validate(record, now)
        if reasons:
            quarantined.append({"observation": record, "reasons": reasons})
        else:
            accepted.append(record)
    result = {"checked_at_utc": now.isoformat(), "accepted": accepted,
              "quarantined": quarantined, "certified_take_count": 0,
              "note": "Data validation is not model certification or betting approval"}
    json.dump(result, sys.stdout, indent=2)
    print()

if __name__ == "__main__":
    main()
