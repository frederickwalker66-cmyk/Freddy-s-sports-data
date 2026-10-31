"""Bounded ESPN NBA historical player box-score research collector.

Player box-score/participation evidence stays separate from team-winner
training. One ESPN source is NOT independent box-score adjudication.
No sportsbook or SportsGameOdds requests; missing stats are never imputed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import sqlite3
from urllib.request import Request, urlopen

SUMMARY_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event="
MAX_GAMES = 5


def _minutes(value):
    if isinstance(value, str) and re.fullmatch(r"\d{1,3}(:[0-5]\d)?", value):
        a = value.split(":")
        n = int(a[0]) + (int(a[1])/60 if len(a)>1 else 0)
        if 0 <= n <= 70:
            return round(n, 3)
    return None


def _number(value):
    if isinstance(value, str) and re.fullmatch(r"\d{1,3}", value):
        return int(value)
    return None


def parse_summary(data, event_id, fetched_at):
    """Fail closed unless exact final event and complete player array."""
    if not isinstance(data, dict):
        raise ValueError("missing NBA summary object")
    header = data.get("header", {})
    competitions = header.get("competitions")
    if not isinstance(competitions, list) or len(competitions) != 1:
        raise ValueError("ambiguous competition header")
    comp = competitions[0]
    if str(comp.get("id")) != str(event_id):
        # ESPN header competition ID is sometimes different from event ID:
        # require explicit header event identity to avoid cross-game mapping.
        pass
    if str(header.get("id")) != str(event_id):
        raise ValueError("ESPN event ID not matching request")
    status = comp.get("status") or {}
    completed = (status.get("type") or {}).get("completed")
    if completed is not True:
        raise ValueError("NBA game not officially marked completed on ESPN")
    teams = comp.get("competitors")
    if not isinstance(teams, list) or len(teams) != 2:
        raise ValueError("incomplete matchup")
    ids = {str(t.get("team", {}).get("id")) for t in teams}
    if len(ids)!=2 or "None" in ids:
        raise ValueError("invalid team ID")
    groups=(data.get("boxscore") or {}).get("players")
    if not isinstance(groups, list) or len(groups)!=2:
        raise ValueError("missing both teams' player boxscore")
    rows=[]
    for group in groups:
        tid = str((group.get("team") or {}).get("id"))
        if tid not in ids:
            raise ValueError("boxscore team inconsistent with game")
        stats = group.get("statistics")
        if not isinstance(stats,list) or not stats:
            raise ValueError("player statistics missing")
        found_ids=set()
        for cat in stats:
            labels=cat.get("labels")
            athletes=cat.get("athletes")
            if not isinstance(labels,list) or not isinstance(athletes,list):
                raise ValueError("malformed player stats")
            for a in athletes:
                player=a.get("athlete") or {}
                pid=str(player.get("id"))
                if not pid.isdigit() or pid in found_ids:
                    raise ValueError("ambiguous player identity")
                found_ids.add(pid)
                dnp=a.get("didNotPlay") is True
                values=a.get("stats")
                if not isinstance(values,list) or len(values)!=len(labels):
                    raise ValueError("partial player boxscore")
                cells=dict(zip(labels,values))
                mins=_minutes(cells.get("MIN"))
                if not dnp and mins is None:
                    raise ValueError("player missing trustworthy minutes")
                if dnp and mins is not None and mins>0:
                    raise ValueError("DNP contradicts positive minutes")
                row={
                    "sport":"nba","event_id":str(event_id),"player_id":pid,
                    "team_id":tid,"player_name":player.get("displayName"),
                    "starter":a.get("starter") is True,
                    "did_not_play":dnp,
                    "minutes":mins,
                    "points":_number(cells.get("PTS")),
                    "rebounds":_number(cells.get("REB")),
                    "assists":_number(cells.get("AST")),
                    "steals":_number(cells.get("STL")),
                    "blocks":_number(cells.get("BLK")),
                    "raw_stat_labels":labels,
                    "raw_stat_values":values,
                    "fetched_at_utc":fetched_at,
                    "source_url":SUMMARY_BASE+str(event_id),
                    "independently_verified_player_stats":False,
                    "historical_prop_settlement_verified":False,
                    "qualified_for_player_prop_training":False,
                    "qualified_for_game_winner_training":False,
                    "champion_001_modified":False,
                }
                if not dnp and (row["points"] is None or row["rebounds"] is None or row["assists"] is None):
                    raise ValueError("key numeric NBA statistics unavailable")
                rows.append(row)
        if not found_ids:
            raise ValueError("no player rows for team")
    return rows


def fetch_summary(event_id):
    req=Request(SUMMARY_BASE+event_id,headers={"Accept":"application/json",
                                                "User-Agent":"FreddysPicksResearch/1.0"})
    with urlopen(req, timeout=15) as r:
        raw=r.read(4_000_001)
    if len(raw)>4_000_000:
        raise ValueError("summary exceeds permitted size")
    return json.loads(raw)


def collect(database, limit=MAX_GAMES, fetcher=fetch_summary, now=None):
    if not 1<=limit<=MAX_GAMES:
        raise ValueError("bounded boxscore limit 1-5")
    now=now or datetime.now(timezone.utc)
    with sqlite3.connect(database) as conn:
        archived=conn.execute("""
          SELECT espn_event_id FROM published_games
          WHERE league='nba' AND independently_adjudicated IS NULL
        """ if False else """
          SELECT espn_event_id FROM published_games
          WHERE league='nba' AND historically_qualified_training=0
          ORDER BY start_utc, espn_event_id LIMIT ?
        """,(limit,)).fetchall()
    results=[]; failures=[]
    for (event_id,) in archived:
        try:
            raw=fetcher(str(event_id))
            rows=parse_summary(raw,str(event_id),now.isoformat())
            for row in rows:
                row["source_payload_sha256"]=hashlib.sha256(
                    json.dumps(raw,sort_keys=True,allow_nan=False).encode("utf-8")).hexdigest()
            results.extend(rows)
        except (ValueError, KeyError, TypeError, OSError, TimeoutError) as exc:
            failures.append({"event_id":str(event_id),"reason":type(exc).__name__})
    report={
        "stage":"nba_historical_boxscore_research_only",
        "game_requests_attempted":len(archived),
        "games_with_structurally_valid_boxes":len(archived)-len(failures),
        "player_rows":len(results),"failed_games":failures,
        "independently_verified_player_stats":0,
        "qualified_player_prop_training_rows":0,
        "qualified_game_winner_training_rows":0,
        "wagers_placed":0,"champion_001_modified":False,
        "warning":"ESPN single-provider boxes need independent corroboration and DNP/market settlement rules. No boxscore outcome is a pregame predictor."
    }
    return results,report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--history-db",required=True)
    p.add_argument("--limit",type=int,default=MAX_GAMES)
    p.add_argument("--output-dir",default="player_boxscore_research")
    args=p.parse_args(argv)
    rows,report=collect(args.history_db,args.limit)
    dest=Path(args.output_dir);dest.mkdir(parents=True,exist_ok=True)
    (dest/"nba_player_boxes_research.jsonl").write_text(
        "".join(json.dumps(x,sort_keys=True)+"\n" for x in rows),encoding="utf8")
    (dest/"nba_player_boxscore_report.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
