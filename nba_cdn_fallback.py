"""NBA live game-day player evidence with a strict date-checked mirror fallback.

Neither CDN nor NBA mediaops mirror data is a complete roster, a provider ID
crosswalk, or evidence that a player is cleared to participate or wager on.
"""
from datetime import date
import json
from urllib.request import Request, urlopen

SCOREBOARD = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
BOXSCORE_PREFIX = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_"
MIRROR_SCOREBOARD = "https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData/scoreboard/todaysScoreboard_00.json"
MIRROR_BOXSCORE_PREFIX = "https://nba-prod-us-east-1-mediaops-stats.s3.amazonaws.com/NBA/liveData/boxscore/boxscore_"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*",
           "Origin": "https://www.nba.com",
           "Referer": "https://www.nba.com/",
           "Accept-Language": "en-US,en;q=0.9"}


def _allowed_source(url):
    if url in (SCOREBOARD, MIRROR_SCOREBOARD):
        return True
    for prefix in (BOXSCORE_PREFIX, MIRROR_BOXSCORE_PREFIX):
        if url.startswith(prefix) and url.endswith(".json"):
            gid = url[len(prefix):-5]
            return len(gid) == 10 and gid.isdigit()
    return False


def fetch_json(url):
    if not _allowed_source(url):
        raise ValueError("unsupported NBA source URL")
    with urlopen(Request(url, headers=HEADERS), timeout=12) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000:
        raise ValueError("NBA live response too large")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("invalid NBA response shape")
    return result


def _current_scoreboard(day, json_fetcher):
    failures = []
    for url in (SCOREBOARD, MIRROR_SCOREBOARD):
        try:
            board = json_fetcher(url).get("scoreboard")
            if not isinstance(board, dict):
                raise ValueError("missing scoreboard")
            actual = board.get("gameDate")
            if not isinstance(actual, str) or actual[:10] != day:
                raise ValueError("stale_or_wrong_scoreboard_date")
            games = board.get("games")
            if not isinstance(games, list) or not 1 <= len(games) <= 20:
                raise ValueError("NBA scoreboard empty or invalid")
            return games, url
        except Exception as exc:
            failures.append({"source": url, "error_type": type(exc).__name__})
    raise ValueError("NBA scoreboard date mismatch or source unavailable; no verified same-day game evidence")


def collect_game_day_players(day, json_fetcher=fetch_json):
    """Return source-attributed game evidence; do not auto-approve any prop."""
    date.fromisoformat(day)
    games, scoreboard_url = _current_scoreboard(day, json_fetcher)
    output = {"game_date": day, "source_url": scoreboard_url, "games": [],
              "crosswalk_verified": False, "complete_rosters_verified": False,
              "game_day_active_verified": False}
    errors = []
    for game in games:
        gid = game.get("gameId") if isinstance(game, dict) else None
        if not isinstance(gid, str) or len(gid) != 10 or not gid.isdigit():
            errors.append("invalid_game_id")
            continue
        box = None
        boxurl = None
        for prefix in (BOXSCORE_PREFIX, MIRROR_BOXSCORE_PREFIX):
            candidate_url = prefix + gid + ".json"
            try:
                item = json_fetcher(candidate_url).get("game")
                if not isinstance(item, dict) or item.get("gameId") != gid:
                    raise ValueError("NBA game ID does not match boxscore")
                box, boxurl = item, candidate_url
                break
            except Exception:
                continue
        if box is None:
            errors.append({"game_id": gid, "error_type": "boxscore_unavailable_or_mismatch"})
            continue
        try:
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
        except (ValueError, KeyError, TypeError):
            errors.append({"game_id": gid, "error_type": "invalid_boxscore_player_data"})
    output["requested_games"] = len(games)
    output["fetched_games"] = len(output["games"])
    output["player_entries"] = sum(len(t["players"]) for g in output["games"] for t in g["teams"])
    output["errors"] = errors
    output["status"] = "evidence_downloaded" if not errors and output["player_entries"] else "partial"
    return output
