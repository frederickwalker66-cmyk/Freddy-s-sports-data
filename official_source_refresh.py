"""Fetch official-source evidence only; NEVER manufacture availability clearance.

Evidence snapshots are NOT provider-to-league ID mappings, confirmed participation,
calibrated forecasts, or bet-ready signals. All URL and JSON failures are reported.
"""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

NBA_INDEX = "https://official.nba.com/nba-injury-report-2026-27-season/"
MLB = "https://statsapi.mlb.com/api/v1"

def fetch(url, max_bytes=5_000_000, timeout=20):
    req = Request(url, headers={"User-Agent": "FreddysPicks-ResearchValidation/1.0", "Accept": "application/json,text/html,application/pdf"})
    with urlopen(req, timeout=timeout) as r:
        data = r.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("oversized official response")
        return data

def get_json(url):
    obj = json.loads(fetch(url))
    if not isinstance(obj, dict):
        raise ValueError("unexpected official JSON shape")
    return obj

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            x = dict(attrs).get("href", "")
            if isinstance(x, str):
                self.hrefs.append(x)

def latest_nba_report(index_html, today):
    from urllib.parse import urljoin, urlparse
    parser = Links()
    parser.feed(index_html)
    items = []
    for href in parser.hrefs:
        url = urljoin(NBA_INDEX, href)
        p = urlparse(url)
        if p.hostname != "ak-static.cms.nba.com":
            continue
        m = re.search(r"Injury-Report_(\\d{4}-\\d{2}-\\d{2})_(\\d{2})_(\\d{2})(AM|PM)\\.pdf$", p.path)
        if m and m.group(1) == today:
            hour = int(m.group(2)) % 12 + (12 if m.group(4) == "PM" else 0)
            minute = int(m.group(3))
            if hour <= 23 and minute <= 59:
                items.append((hour, minute, url))
    return max(items)[2] if items else None

def refresh(today=None, outdir="official_sources", fetcher=fetch, json_fetcher=get_json):
    root = Path(outdir)
    root.mkdir(parents=True, exist_ok=True)
    current = datetime.now(timezone.utc)
    date = today or current.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    report = {"retrieved_at_utc": current.isoformat(), "game_date_et": date,
              "purpose": "source_evidence_only_not_player_availability",
              "sources": {}, "player_props_cleared": 0,
              "model_probabilities_generated": 0,
              "champion_001_modified": False}
    # The official injury PDF is evidence only. It does not include every healthy
    # player, so absence of a name MUST NOT mean 'available'.
    try:
        html = fetcher(NBA_INDEX, max_bytes=1_500_000).decode("utf-8")
        latest = latest_nba_report(html, date)
        if not latest:
            raise ValueError("No current-day NBA official injury PDF link")
        pdf = fetcher(latest, max_bytes=7_000_000)
        if not pdf.startswith(b"%PDF"):
            raise ValueError("Invalid NBA injury report payload")
        (root / "nba_injury_report.pdf").write_bytes(pdf)
        report["sources"]["nba"] = {"status": "evidence_downloaded", "url": latest,
                                    "bytes": len(pdf), "player_status_parsed": False,
                                    "roster_synced": False}
    except (Exception) as exc:
        report["sources"]["nba"] = {"status": "unavailable", "error_type": type(exc).__name__,
                                    "player_status_parsed": False, "roster_synced": False}
    # MLB active rosters use native MLB IDs. These IDs are NOT the odds-provider IDs.
    try:
        teams_url = MLB + "/teams?" + urlencode({"sportId": 1, "season": int(date[:4])})
        teams = json_fetcher(teams_url).get("teams", [])
        if not isinstance(teams, list) or len(teams) < 25:
            raise ValueError("MLB team discovery incomplete")
        active = []
        failed = []
        for team in teams:
            tid = team.get("id")
            if not isinstance(tid, int):
                failed.append("missing_team_id")
                continue
            url = MLB + f"/teams/{tid}/roster?" + urlencode({"rosterType": "active", "date": date})
            try:
                data = json_fetcher(url)
                players = data.get("roster")
                if not isinstance(players, list):
                    raise ValueError("MLB roster response incomplete")
                active.append({"team_id": tid, "team_name": team.get("name"),
                               "source_url": url,
                               "players": [{"official_player_id": p.get("person", {}).get("id"),
                                            "player_name": p.get("person", {}).get("fullName"),
                                            "status": p.get("status")} for p in players]})
            except (Exception) as exc:
                failed.append({"team_id": tid, "error_type": type(exc).__name__})
            time.sleep(0.1)
        (root / "mlb_active_rosters.json").write_text(json.dumps({"date_et": date, "teams": active}, indent=2))
        report["sources"]["mlb_roster"] = {"status": "complete" if not failed and len(active) == len(teams) else "partial",
                                          "team_count": len(teams), "fetched_teams": len(active),
                                          "failed": failed[:15], "provider_id_crosswalk_verified": False}
    except (Exception) as exc:
        report["sources"]["mlb_roster"] = {"status": "unavailable", "error_type": type(exc).__name__,
                                          "provider_id_crosswalk_verified": False}
    # Pull scheduled MLB games and any lineup currently present in MLB box scores.
    try:
        schedule_url = MLB + "/schedule?" + urlencode({"sportId": 1, "date": date})
        dates = json_fetcher(schedule_url).get("dates", [])
        games = []
        errors = []
        for day in dates:
            for game in day.get("games", []):
                game_id = game.get("gamePk")
                if not isinstance(game_id, int):
                    continue
                boxurl = MLB + f"/game/{game_id}/boxscore"
                try:
                    box = json_fetcher(boxurl)
                    teams = box.get("teams", {})
                    sides = {}
                    for side in ("home", "away"):
                        x = teams.get(side, {})
                        sides[side] = {"official_team_id": x.get("team", {}).get("id"),
                                       "batting_order_official_ids": x.get("battingOrder", []),
                                       "source_url": boxurl}
                    games.append({"game_id": game_id, "game_status": game.get("status", {}),
                                  "home": sides["home"], "away": sides["away"]})
                except (Exception) as exc:
                    errors.append({"game_id": game_id, "error_type": type(exc).__name__})
        (root / "mlb_lineup_evidence.json").write_text(json.dumps({"date_et": date, "games": games}, indent=2))
        report["sources"]["mlb_lineups"] = {
            "status": "complete" if not errors else "partial", "games_fetched": len(games),
            "errors": errors, "lineups_confirmed_as_playing": False,
            "provider_id_crosswalk_verified": False}
    except (Exception) as exc:
        report["sources"]["mlb_lineups"] = {"status": "unavailable", "error_type": type(exc).__name__,
                                           "lineups_confirmed_as_playing": False}
    # NFL official reports exist, but no tested, consistent per-player ingestion
    # is configured. Fail closed rather than treating unknown as cleared.
    report["sources"]["nfl"] = {"status": "not_connected",
                                 "official_resource": "https://www.nfl.com/injuries/",
                                 "player_status_parsed": False, "game_day_actives_verified": False}
    (root / "source_refresh_report.json").write_text(json.dumps(report, indent=2))
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="official_sources")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    summary = refresh(args.date, args.outdir)
    print(json.dumps(summary, indent=2))
