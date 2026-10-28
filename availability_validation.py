"""Game-day availability gate for player props; missing source evidence fails closed.

Manifests are independently reviewed evidence, NOT live data feeds. A URL alone
does not verify that the source was fetched or that a player is cleared.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

OFFICIAL_DOMAINS = {"nba": ("nba.com", "official.nba.com"),
                    "nfl": ("nfl.com",),
                    "mlb": ("mlb.com", "statsapi.mlb.com")}
MAX_STATUS_AGE_SECONDS = 7200
ALLOW_STATUSES = {"available"}
ALLOW_LINEUP = {"nba": {"confirmed_active"},
                "nfl": {"confirmed_active"},
                "mlb": {"confirmed_lineup"}}


def _utc(s):
    if not isinstance(s, str) or not s.strip():
        raise ValueError("missing timestamp")
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("missing time offset")
    return d.astimezone(timezone.utc)


def _id(x):
    if isinstance(x, bool) or not isinstance(x, (int, str)):
        return None
    return str(x).strip() or None


def _canonical(x):
    return " ".join(x.strip().casefold().split()) if isinstance(x, str) else ""


def _official(url, league):
    if not isinstance(url, str):
        return False
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host == d or host.endswith("." + d)
        for d in OFFICIAL_DOMAINS.get(league, ()))


def load_availability(path):
    """Explicit review manifest: data are not independently verified by this loader."""
    if path is None:
        return {}
    import json
    from pathlib import Path
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("players"), list):
        raise ValueError("availability.players must be a list")
    found = {}
    for row in raw["players"]:
        if not isinstance(row, dict) or not _id(row.get("provider_player_id")):
            raise ValueError("missing availability identity")
        league = row.get("league")
        if (league not in OFFICIAL_DOMAINS
            or not _official(row.get("source_url"), league)
            or not _canonical(row.get("player_name"))
            or not isinstance(row.get("team"), str) or not row["team"].strip()
            or not isinstance(row.get("event_id"), str) or not row["event_id"].strip()):
            raise ValueError("invalid game-day source or identity")
        _utc(row.get("verified_at_utc"))
        key = (league, _id(row["provider_player_id"]), row["event_id"])
        if key in found:
            raise ValueError("duplicate game-day status")
        found[key] = row
    return found


def check_availability(row, statuses):
    """Any unknown/ambiguous/reported-risk status blocks research-stage prop."""
    league = row.get("league")
    key = (league, _id(row.get("player_id")), row.get("event_id"))
    try:
        item = statuses.get(key)
    except TypeError:
        item = None
    if not item:
        return ["game_day_status_not_verified"]
    reasons = []
    if _canonical(row.get("player_name")) != _canonical(item.get("player_name")):
        reasons.append("game_day_player_mismatch")
    if item.get("team") not in (row.get("home_team"), row.get("away_team")):
        reasons.append("game_day_team_mismatch")
    if item.get("injury_status") not in ALLOW_STATUSES:
        reasons.append("player_injury_status_not_cleared")
    if item.get("lineup_status") not in ALLOW_LINEUP.get(league, set()):
        reasons.append("game_day_lineup_or_active_status_unconfirmed")
    if not _official(item.get("source_url"), league):
        reasons.append("game_day_source_unofficial")
    try:
        collected = _utc(row.get("recorded_at"))
        reviewed = _utc(item.get("verified_at_utc"))
        age = (collected - reviewed).total_seconds()
        if age < 0 or age > MAX_STATUS_AGE_SECONDS:
            reasons.append("game_day_report_stale_or_future")
    except (TypeError, ValueError, OverflowError):
        reasons.append("game_day_report_time_invalid")
    return sorted(set(reasons))
