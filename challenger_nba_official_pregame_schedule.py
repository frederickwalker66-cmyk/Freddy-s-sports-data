"""#78 independently observe NBA-operated pregame game IDs (research only).

Use only NBA-owned original source bytes, exact pregame fetch timestamps,
canonical URLs, ten-digit game IDs, league/team IDs, and home/away identity.
No cached scoreboard or publisher publication timestamp is inferred.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import json
import re

from challenger_nba_schedule_clock import (
    NBA_SCHEDULE_URL, NBA_TODAY_SCOREBOARD_URL,
    nba_team_name, official_nba_events, stats_scoreboard_url,
)
from challenger_nba_daily_scoreboard_fallback import (
    validate_same_day_scoreboard, source_game_records,
)
from challenger_nba_stats_v3_schedule_fallback import verify_stats_v3_scoreboard
from challenger_nba_pregame_roster_identity import fetch_source, MAX_SCHEDULE_BYTES
from challenger_nba_injury_pdf_player_rows import TEAM_CODES, TEAMS

NBA_TEAM_IDS_BY_CODE = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751,
    "CHA": 1610612766, "CHI": 1610612741, "CLE": 1610612739,
    "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765,
    "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763,
    "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750,
    "NOP": 1610612740, "NYK": 1610612752, "OKC": 1610612760,
    "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759,
    "TOR": 1610612761, "UTA": 1610612762, "WAS": 1610612764,
}
CANONICAL_IDS = {
    nba_team_name(name): str(NBA_TEAM_IDS_BY_CODE[code])
    for code, name in TEAM_CODES.items()
}
MAX_GAMES = 1500


def fetch_original(url):
    """Bounded league-owned fetch, with no proxies or access-denial bypass."""
    return fetch_source(url, MAX_SCHEDULE_BYTES)


def parse_original(raw, source_url, observed_at):
    """Validate and return a single NBA original-response receipt's future games.

    Season schedule covers upcoming days. Today's CDN or Stats V3 scoreboard
    is only valid for the Eastern calendar day of its actual observation.
    """
    if (not isinstance(observed_at, datetime) or observed_at.tzinfo is None
            or not isinstance(raw, bytes)
            or not 1 <= len(raw) <= MAX_SCHEDULE_BYTES):
        raise ValueError("nba_original_response_requires_bounded_bytes_and_aware_clock")
    seen_at = observed_at.astimezone(timezone.utc)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("nba_original_source_must_be_object")
    if source_url == NBA_SCHEDULE_URL:
        league = payload.get("leagueSchedule")
        if (not isinstance(league, dict) or league.get("leagueId") != "00"
                or not isinstance(league.get("gameDates"), list)):
            raise ValueError("nba_official_season_wrong_league_or_schema")
        games = [g for group in league["gameDates"]
                 for g in group.get("games", [])] if all(
                 isinstance(group, dict) and isinstance(group.get("games"), list)
                 for group in league["gameDates"]) else None
        if not isinstance(games, list) or len(games) > MAX_GAMES:
            raise ValueError("nba_official_season_games_invalid")
        kind = "nba_season_schedule"
        records = official_nba_events(payload)
    elif source_url == NBA_TODAY_SCOREBOARD_URL:
        payload, records = validate_same_day_scoreboard(raw, seen_at)
        kind = "nba_daily_scoreboard"
    else:
        # NBA Stats ScoreboardV3 is date-addressable. On a hosted runner,
        # the league's season CDN can be unavailable even when tomorrow's
        # ESPN pregame events exist. Permit only canonical Stats dates
        # between the real Eastern observation day and seven days ahead;
        # this is research game identity, not pregame player clearance.
        from challenger_nba_schedule_clock import NBA_STATS_SCOREBOARD_V3
        prefix = NBA_STATS_SCOREBOARD_V3 + "?GameDate="
        if not isinstance(source_url, str) or not source_url.startswith(prefix):
            raise ValueError("nba_official_schedule_source_url_not_allowed")
        day = source_url[len(prefix):].split("&", 1)[0]
        if source_url != stats_scoreboard_url(day):
            raise ValueError("nba_official_schedule_source_url_not_allowed")
        today_et = seen_at.astimezone(ZoneInfo("America/New_York")).date()
        target_et = datetime.fromisoformat(day).date()
        if not today_et <= target_et <= today_et + timedelta(days=7):
            raise ValueError("nba_official_future_scoreboard_day_outside_window")
        payload, records = verify_stats_v3_scoreboard(
            raw, source_url, seen_at, event_day_et=day)
        kind = ("nba_stats_scoreboard_v3" if target_et == today_et
                else "nba_stats_scoreboard_v3_future_date")
    team_ids, _ = source_game_records(payload)
    if (not set(g["official_nba_game_id"] for g in records).issubset(team_ids)
            or (kind == "nba_season_schedule" and len(records) != len(team_ids))):
        raise ValueError("nba_scheduled_game_ids_not_fully_reconciled")
    unique = set()
    clean = []
    for game in records:
        gid = game["official_nba_game_id"]
        if not isinstance(gid, str) or re.fullmatch(r"\d{10}", gid) is None or gid in unique:
            raise ValueError("nba_official_game_id_invalid_or_duplicate")
        unique.add(gid)
        home, away = game["home"], game["away"]
        if (home not in TEAMS or away not in TEAMS or home == away
                or team_ids[gid]["home"] != CANONICAL_IDS[home]
                or team_ids[gid]["away"] != CANONICAL_IDS[away]):
            raise ValueError("nba_official_team_id_name_pair_inconsistent")
        if game["start"] <= seen_at:
            # The original record is not new pregame identity proof at or after tip.
            continue
        clean.append({
            "nba_game_id": gid, "start": game["start"],
            "home_name": home, "away_name": away,
            "home_id": team_ids[gid]["home"], "away_id": team_ids[gid]["away"],
            "source_kind": kind,
        })
    return clean, hashlib.sha256(raw).hexdigest(), kind
