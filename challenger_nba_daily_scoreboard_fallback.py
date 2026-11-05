"""Strict same-day NBA-operated daily scoreboard validator for pregame identity.

The scoreboard is a fallback when the NBA season schedule cannot be obtained.
Do not accept yesterday's cached board, a different league, missing team IDs,
an ambiguous game, or a game already underway as a pregame schedule.
Original JSON bytes and actual capture time remain essential; no betting.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import re
from zoneinfo import ZoneInfo

from challenger_nba_schedule_clock import official_nba_events, nba_team_name
from challenger_nba_injury_pdf_player_rows import TEAMS

EASTERN = ZoneInfo("America/New_York")
MAX_BYTES = 18_000_000
MAX_GAMES_ON_DAY = 25


def validate_same_day_scoreboard(raw, captured_at):
    if (not isinstance(captured_at, datetime) or captured_at.tzinfo is None
            or not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES):
        raise ValueError("nba_scoreboard_requires_original_bytes_and_aware_capture")
    now = captured_at.astimezone(timezone.utc)
    doc = json.loads(raw)
    if not isinstance(doc, dict) or not isinstance(doc.get("scoreboard"), dict):
        raise ValueError("unrecognized_nba_daily_scoreboard_schema")
    board = doc["scoreboard"]
    day = board.get("gameDate")
    if (not isinstance(day, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) is None
            or date.fromisoformat(day) != now.astimezone(EASTERN).date()
            or board.get("leagueId") != "00"):
        raise ValueError("stale_or_wrong_league_nba_daily_scoreboard")
    games = board.get("games")
    if not isinstance(games, list) or len(games) > MAX_GAMES_ON_DAY:
        raise ValueError("oversized_or_missing_nba_daily_scoreboard_games")
    seen = set()
    for g in games:
        if not isinstance(g, dict):
            raise ValueError("invalid_nba_daily_scoreboard_game_object")
        gid = str(g.get("gameId"))
        if re.fullmatch(r"\d{10}", gid) is None or gid in seen:
            raise ValueError("duplicate_or_invalid_nba_daily_game_identity")
        seen.add(gid)
        if g.get("gameStatus") not in (1, "1", 2, "2", 3, "3"):
            raise ValueError("unrecognized_nba_daily_game_status")
        teams = []
        for side in ("home", "away"):
            team = g.get(side + "Team")
            if not isinstance(team, dict):
                raise ValueError("nba_daily_scoreboard_team_missing")
            name = nba_team_name(str(team.get("teamCity") or "") + " " +
                                 str(team.get("teamName") or ""))
            tid = team.get("teamId")
            if (name not in TEAMS or type(tid) not in (int, str)
                    or not str(tid).isdigit() or int(tid) <= 0):
                raise ValueError("nba_daily_scoreboard_team_identity_not_official")
            teams.append((name, str(tid)))
        if teams[0][0] == teams[1][0] or teams[0][1] == teams[1][1]:
            raise ValueError("nba_daily_scoreboard_same_team_on_two_sides")
    scheduled = official_nba_events(doc)
    if len(scheduled) != sum(g.get("gameStatus") in (1, "1") for g in games):
        raise ValueError("nba_daily_scoreboard_invalid_scheduled_event")
    # A game still marked scheduled after its scheduled tipoff is NOT
    # retroactively usable as a future pregame event.
    future = [g for g in scheduled if g["start"] > now]
    return doc, future


def source_game_records(payload):
    """Extract team IDs from either official season schedule or daily scoreboard.

    For the daily board, the caller must first validate same-day identity and
    retain the original capture timestamp/sha in its source receipt.
    """
    if not isinstance(payload, dict):
        raise ValueError("invalid_official_schedule_identity_document")
    if isinstance(payload.get("leagueSchedule"), dict):
        groups = payload["leagueSchedule"].get("gameDates")
        if not isinstance(groups, list):
            raise ValueError("missing_official_season_game_groups")
        raw_games = [g for group in groups for g in group.get("games", [])
                     if isinstance(group, dict)]
        kind = "nba_season_schedule"
    elif isinstance(payload.get("scoreboard"), dict):
        raw_games = payload["scoreboard"].get("games")
        if not isinstance(raw_games, list):
            raise ValueError("missing_official_daily_scoreboard_games")
        kind = "nba_daily_scoreboard_same_day_fallback"
    else:
        raise ValueError("unrecognized_official_nba_game_source_kind")
    ids = {}
    for game in raw_games:
        if not isinstance(game, dict) or game.get("gameStatus") not in (1, "1"):
            continue
        gid = str(game.get("gameId"))
        if re.fullmatch(r"\d{10}", gid) is None or gid in ids:
            raise ValueError("invalid_or_duplicate_official_nba_game_id")
        h, a = game.get("homeTeam"), game.get("awayTeam")
        if not isinstance(h, dict) or not isinstance(a, dict):
            raise ValueError("missing_official_nba_team_records")
        if (type(h.get("teamId")) not in (int, str)
                or type(a.get("teamId")) not in (int, str)
                or not str(h["teamId"]).isdigit()
                or not str(a["teamId"]).isdigit()
                or str(h["teamId"]) == str(a["teamId"])):
            raise ValueError("invalid_official_nba_team_ids")
        ids[gid] = {"home": str(h["teamId"]), "away": str(a["teamId"])}
    return ids, kind
