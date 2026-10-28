"""Independent roster identity gate for research staging. No roster-feed automation.

A curated manifest must be checked against official league rosters, and must map
provider player IDs to independently verified official IDs. Absence fails closed.
An active roster listing does NOT prove a player will play or is cleared to bet.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse

MAX_ROSTER_AGE_SECONDS = 86400
OFFICIAL_DOMAINS = {"nba": "nba.com", "nfl": "nfl.com", "mlb": "mlb.com"}


def parse_utc(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("roster verification timestamp missing")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("roster timestamp needs UTC offset")
    return dt.astimezone(timezone.utc)


def canonical_name(value):
    return " ".join(value.strip().casefold().split()) if isinstance(value, str) else ""


def identity(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    return str(value).strip() or None


def official_url(url, league):
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    domain = OFFICIAL_DOMAINS.get(league)
    return parsed.scheme == "https" and bool(domain) and (
        host == domain or host.endswith("." + domain))


def load_rosters(path):
    """Require source-attributed, externally reviewed player/team/ID mappings.

    Source URLs and timestamps are *claims* in a file, not evidence that they
    have been fetched or independently verified automatically.
    """
    if path is None:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("players"), list):
        raise ValueError("rosters.players must be a list")
    by_provider_id = {}
    for row in data["players"]:
        if not isinstance(row, dict):
            raise ValueError("invalid roster record")
        league = row.get("league")
        provider_id = identity(row.get("provider_player_id"))
        official_id = identity(row.get("official_player_id"))
        if (not provider_id or not official_id or not canonical_name(row.get("player_name"))
                or not isinstance(row.get("team"), str) or not row["team"].strip()
                or not isinstance(row.get("status"), str)
                or not official_url(row.get("source_url"), league)):
            raise ValueError("roster player missing authoritative identification")
        parse_utc(row.get("verified_at_utc"))
        key = (league, provider_id)
        if key in by_provider_id:
            raise ValueError("duplicate provider player ID in roster manifest")
        by_provider_id[key] = row
    return by_provider_id


def check_player_roster(row, rosters):
    """Return quarantine causes for any unverified, stale or mismatched prop."""
    player_id = identity(row.get("player_id"))
    league = row.get("league")
    if not player_id or not isinstance(league, str):
        return ["roster_not_independently_verified"]
    roster = rosters.get((league, player_id))
    if roster is None:
        return ["roster_not_independently_verified"]
    reasons = []
    if canonical_name(row.get("player_name")) != canonical_name(roster.get("player_name")):
        reasons.append("roster_player_name_mismatch")
    if roster.get("team") not in (row.get("home_team"), row.get("away_team")):
        reasons.append("roster_team_not_in_event")
    if roster.get("status") != "active":
        reasons.append("player_not_active_on_roster")
    try:
        observed = parse_utc(row.get("recorded_at"))
        verified = parse_utc(roster.get("verified_at_utc"))
        age = (observed - verified).total_seconds()
        if age < 0 or age > MAX_ROSTER_AGE_SECONDS:
            reasons.append("roster_stale_or_future")
    except (ValueError, TypeError, OverflowError):
        reasons.append("roster_unverified_time")
    return reasons
