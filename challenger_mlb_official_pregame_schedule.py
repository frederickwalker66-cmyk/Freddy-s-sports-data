"""Read-only MLB-operated Stats API schedule evidence for Challenger #77.

This parser accepts original source bytes for one exact schedule date and
extracts gamePk, exact home/away MLB IDs and full names, and UTC first pitch.
No sportsbook quotes, feature values, probabilities or bets are produced.
"""
from __future__ import annotations

from datetime import date
import json
from urllib.request import Request, urlopen

from challenger_prospective_outcome_validation import instant

BASE = "https://statsapi.mlb.com/api/v1/schedule"
MAX_BYTES = 3_000_000
PREGAME_TYPES = {"Preview"}
# MLB's named playoff rounds are distinct from regular-season and exhibition.
COMPETITIVE_GAME_TYPES = {"R", "P", "F", "D", "L", "W"}


def day_url(day):
    """The URL is canonical and derived from an exact ISO calendar date."""
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("invalid_official_mlb_schedule_date")
    return BASE + "?sportId=1&date=" + day


def fetch_schedule(day):
    request = Request(day_url(day), headers={
        "Accept": "application/json",
        "User-Agent": "FreddysPicks-ChallengerOfficialMLBIdentity/1.0",
    })
    with urlopen(request, timeout=15) as response:
        raw = response.read(MAX_BYTES + 1)
    if not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("invalid_official_mlb_response_size")
    return raw


def normalized_name(value):
    return " ".join(value.casefold().split()) if isinstance(value, str) else ""


def parse_schedule(raw, requested_day):
    """Reject wrong-date, duplicated or malformed MLB source payloads.

    A game may have an official stadium-local date one calendar day earlier
    than its start in Eastern time. The caller chooses the bounded dates to
    request; this parser never rewrites an actual first-pitch instant.
    """
    day_url(requested_day)
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_BYTES:
        raise ValueError("invalid_official_mlb_original_bytes")
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not isinstance(obj.get("dates"), list):
        raise ValueError("invalid_official_mlb_schedule_response")
    if len(obj["dates"]) > 2:
        raise ValueError("official_mlb_unexpected_date_slots")
    seen = set()
    games = []
    for slot in obj["dates"]:
        if (not isinstance(slot, dict) or slot.get("date") != requested_day
                or not isinstance(slot.get("games"), list)
                or len(slot["games"]) > 50):
            raise ValueError("official_mlb_schedule_date_or_schema_mismatch")
        for game in slot["games"]:
            if not isinstance(game, dict):
                raise ValueError("official_mlb_game_not_object")
            game_id = game.get("gamePk")
            if type(game_id) is not int or game_id <= 0 or game_id in seen:
                raise ValueError("missing_or_duplicate_official_mlb_game_id")
            seen.add(game_id)
            if game.get("officialDate") not in (None, requested_day):
                raise ValueError("official_mlb_game_date_contradicts_requested_day")
            start = instant(game.get("gameDate"))
            raw_teams = game.get("teams")
            if not isinstance(raw_teams, dict):
                raise ValueError("official_mlb_game_teams_missing")
            teams = {}
            for side in ("home", "away"):
                node = raw_teams.get(side)
                team = node.get("team") if isinstance(node, dict) else None
                tid = team.get("id") if isinstance(team, dict) else None
                name = team.get("name") if isinstance(team, dict) else None
                if (type(tid) is not int or tid <= 0
                        or not normalized_name(name)):
                    raise ValueError("official_mlb_team_id_or_name_invalid")
                teams[side] = (tid, name)
            if teams["home"][0] == teams["away"][0]:
                raise ValueError("official_mlb_home_away_team_ids_identical")
            state = game.get("status")
            if not isinstance(state, dict):
                raise ValueError("official_mlb_game_status_missing")
            # Finished, live, canceled and postponed games are not eligible
            # for a pregame identity assertion, even if a response is fresh.
            if (state.get("abstractGameState") not in PREGAME_TYPES
                    or game.get("gameType") not in COMPETITIVE_GAME_TYPES):
                continue
            detail = normalized_name(state.get("detailedState"))
            if any(x in detail for x in ("postpon", "cancel", "suspend", "delay")):
                continue
            games.append({
                "mlb_game_pk": str(game_id),
                "start": start,
                "home_id": teams["home"][0],
                "away_id": teams["away"][0],
                "home_name": teams["home"][1],
                "away_name": teams["away"][1],
                "game_type": game["gameType"],
                "schedule_date": requested_day,
            })
    return games
