"""Read-only live NFL results; no prediction or sportsbook settlement claims."""
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
def fetch(endpoint, params):
    url = BASE + endpoint + "?" + urlencode(params)
    with urlopen(Request(url, headers={"User-Agent": "FreddysLiveResearch/1.0"}), timeout=12) as response:
        return json.load(response)

def collect(day=None, getter=fetch):
    day = day or datetime.now(ZoneInfo("America/New_York")).date()
    report = {"source":"ESPN", "retrieved_utc":datetime.now(timezone.utc).isoformat(),
              "games":[], "errors":[], "champion_modified":False,
              "sportsbook_settlement_verified":False}
    try:
        events = getter("scoreboard", {"dates":day.strftime("%Y%m%d")})["events"]
    except Exception as exc:
        report["errors"].append(type(exc).__name__)
        return dict(report, status="UNAVAILABLE")
    for event in events:
        try:
            competition = event["competitions"][0]
            status = competition["status"]
            game = {"id":str(event["id"]), "start":event["date"],
                    "state":status["type"]["state"], "completed":status["type"]["completed"],
                    "clock":status.get("displayClock"), "period":status.get("period"),
                    "teams":competition["competitors"], "players":[], "boxscore_available":False}
            report["games"].append(game)
            if game["state"] == "pre":
                continue
            box = getter("summary", {"event":game["id"]})["boxscore"]
            for team in box.get("players", []):
                for category in team.get("statistics", []):
                    labels = category.get("keys") or category.get("labels") or []
                    for athlete in category.get("athletes", []):
                        values = athlete.get("stats", [])
                        if len(labels) != len(values):
                            continue
                        game["players"].append({"team":team["team"]["id"],
                            "athlete_id":athlete["athlete"]["id"],
                            "name":athlete["athlete"]["displayName"],
                            "category":category.get("name"),
                            "stats":dict(zip(labels,values))})
            game["boxscore_available"] = bool(game["players"])
            if not game["boxscore_available"]:
                report["errors"].append(game["id"]+":missing_player_stats")
        except Exception as exc:
            report["errors"].append(str(event.get("id"))+":"+type(exc).__name__)
    return dict(report,status="PARTIAL" if report["errors"] else "SOURCE_RESPONSE_RECEIVED")

if __name__ == "__main__":
    print(json.dumps(collect(),indent=2))
