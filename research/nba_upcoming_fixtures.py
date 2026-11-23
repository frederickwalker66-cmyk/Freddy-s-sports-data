"""Fetch actual upcoming NBA fixtures from ESPN public scoreboard, never invent games."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from historical_outcomes import scoreboard_url, fetch_json, parse_time

def upcoming_from_payload(payload, now, source_url):
    result=[]
    for game in payload.get("events",[]):
        if not isinstance(game,dict) or game.get("status",{}).get("type",{}).get("state")!="pre":
            continue
        try:
            start=parse_time(game["date"])
            if start<=now:continue
            teams={c["homeAway"]:c["team"] for c in game["competitions"][0]["competitors"]}
            home,away=teams["home"],teams["away"]
            eid=str(game["id"])
            if not eid.isdigit() or str(home["id"])==str(away["id"]):continue
            result.append({"event_id":eid,"start_utc":start.isoformat(),
                           "home_team_espn_id":str(home["id"]),"away_team_espn_id":str(away["id"]),
                           "home_team":home["displayName"],"away_team":away["displayName"],
                           "source_url":source_url})
        except (KeyError,TypeError,ValueError,IndexError):
            continue
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",default="upcoming_nba.json")
    args=p.parse_args()
    now=datetime.now(timezone.utc)
    # Query today and tomorrow in UTC so late Eastern fixtures aren't lost.
    events={}
    for day in (now.date(),__import__("datetime").timedelta(days=1)+now.date()):
        url=scoreboard_url("nba",day)
        for event in upcoming_from_payload(fetch_json(url),datetime.now(timezone.utc),url):
            events[event["event_id"]]=event
    out=sorted(events.values(),key=lambda e:(e["start_utc"],e["event_id"]))
    Path(args.output).write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({"upcoming_nba_fixtures":len(out),"source":"ESPN public scoreboard","certified":False}))

if __name__=="__main__":main()
