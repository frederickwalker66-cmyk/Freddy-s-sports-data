"""Official NBA CDN game-day player/team evidence; NOT a complete roster.

NBA liveData boxscores may omit players before tipoff and can reflect substitutions
or inactive listings. This module deliberately never certifies participation,
player-ID crosswalks, or sportsbook props.
"""
from datetime import date
import json
from urllib.request import Request, urlopen

SCOREBOARD = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
BOXSCORE_PREFIX = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
           "Referer": "https://www.nba.com/"}


def fetch_json(url):
    if not (url == SCOREBOARD or
            (url.startswith(BOXSCORE_PREFIX)
             and url.endswith(".json")
             and url[len(BOXSCORE_PREFIX):-5].isdigit()
             and len(url[len(BOXSCORE_PREFIX):-5]) == 10)):
        raise ValueError("unsupported NBA source URL")
    with urlopen(Request(url, headers=HEADERS), timeout=12) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError("NBA CDN response too large")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("invalid NBA response shape")
    return result


def collect_game_day_players(day, json_fetcher=fetch_json):
    """Return an attributed evidence snapshot, never a vetted roster manifest."""
    date.fromisoformat(day)
    url = SCOREBOARD
    board = json_fetcher(url).get("scoreboard")
    if not isinstance(board, dict):
        raise ValueError("missing NBA scoreboard")
    actual_date = board.get("gameDate", "")
    if not isinstance(actual_date, str) or actual_date[:10] != day:
        raise ValueError("NBA scoreboard date mismatch")
    games = board.get("games")
    if not isinstance(games, list) or not 1 <= len(games) <= 20:
        raise ValueError("NBA scoreboard empty or invalid")
    output = {"game_date": day, "source_url": url, "games": [],
              "crosswalk_verified": False, "complete_rosters_verified": False,
              "game_day_active_verified": False}
    errors = []
    for game in games:
        gid = game.get("gameId") if isinstance(game, dict) else None
        if not isinstance(gid, str) or len(gid) != 10 or not gid.isdigit():
            errors.append("invalid_game_id")
            continue
        boxurl = BOXSCORE_PREFIX + gid + ".json"
        try:
            box = json_fetcher(boxurl).get("game")
            if not isinstance(box, dict) or box.get("gameId") != gid:
                raise ValueError("game ID does not match boxscore")
            teams = []
            for side in ("homeTeam", "awayTeam"):
                team = box.get(side)
                if not isinstance(team, dict) or not isinstance(team.get("players"), list):
                    raise ValueError("team players missing")
                tid = team.get("teamId")
                if isinstance(tid, bool) or not isinstance(tid, int):
                    raise ValueError("team ID invalid")
                players = []
                for p in team["players"]:
                    if not isinstance(p, dict):
                        continue
                    pid = p.get("personId")
                    name = p.get("name")
                    if isinstance(pid, int) and not isinstance(pid, bool) and isinstance(name, str) and name.strip():
                        players.append({"official_player_id": pid,
                                        "name": name,
                                        "source_status": p.get("status"),
                                        "not_playing_reason": p.get("notPlayingReason")})
                teams.append({"side": side, "official_team_id": tid,
                              "team_name": team.get("teamName"),
                              "team_city": team.get("teamCity"),
                              "team_tricode": team.get("teamTricode"),
                              "players": players})
            output["games"].append({"game_id": gid, "game_status": box.get("gameStatus"),
                                    "boxscore_url": boxurl, "teams": teams})
        except (ValueError, KeyError, TypeError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            errors.append({"game_id": gid, "error_type": type(exc).__name__})
    output["requested_games"] = len(games)
    output["fetched_games"] = len(output["games"])
    output["player_entries"] = sum(len(t["players"]) for g in output["games"] for t in g["teams"])
    output["errors"] = errors
    output["status"] = "evidence_downloaded" if not errors and output["player_entries"] else "partial"
    return output
