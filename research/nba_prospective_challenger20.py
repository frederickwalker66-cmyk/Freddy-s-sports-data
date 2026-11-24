"""Prospective NBA Challenger-001 20-point Elo research forecasts.

Forecasts are generated from embargoed historical results before tipoff.
Artifacts are immutable per workflow run, but this is not independent
timestamp authentication or betting certification.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from challenger_elo_walkforward import validate_game, K, SETTLEMENT_LAG_HOURS

HOME_ADV = 20.0

def run(history, fixtures, now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ratings, seen = {}, set()
    past = []
    for row in history:
        lg, dt, eid, home, away, outcome = validate_game(row)
        if lg != "nba" or outcome is None:
            continue
        if eid in seen:
            raise ValueError("duplicate historical event")
        seen.add(eid)
        if dt + timedelta(hours=SETTLEMENT_LAG_HOURS) <= now:
            past.append((dt,eid,home,away,outcome))
    for _,eid,home,away,y in sorted(past):
        a,b=ratings.get(home,1500.),ratings.get(away,1500.)
        p=1/(1+10**((b-a-HOME_ADV)/400))
        ratings[home]=a+K*(y-p)
        ratings[away]=b-K*(y-p)
    forecasts=[]
    fixture_ids=set()
    for event in fixtures:
        eid=event["event_id"]
        start=datetime.fromisoformat(event["start_utc"].replace("Z","+00:00"))
        home,away=event["home_team_espn_id"],event["away_team_espn_id"]
        if eid in seen or eid in fixture_ids or start <= now or home==away:
            raise ValueError("duplicate, historical, or started fixture")
        fixture_ids.add(eid)
        if not event.get("source_url","").startswith("https://"):
            raise ValueError("source URL required")
        a,b=ratings.get(home,1500.),ratings.get(away,1500.)
        p=1/(1+10**((b-a-HOME_ADV)/400))
        forecasts.append({
            "event_id":eid,"home_team":event["home_team"],"away_team":event["away_team"],
            "home_team_espn_id":str(home),"away_team_espn_id":str(away),
            "start_utc":start.isoformat(),"forecast_created_utc":now.isoformat(),
            "home_win_probability":round(p,6),"away_win_probability":round(1-p,6),
            "source_url":event["source_url"],"model":"Challenger-001 20-point Elo research",
            "decision":"HOLD","certified":False,"bet_ready":False})
    return {"created_utc":now.isoformat(),"home_advantage_elo":HOME_ADV,
            "historical_games_used":len(past),"forecasts":forecasts,
            "champion_001_modified":False,"certified_take_count":0,
            "calibrated":False,"independently_timestamp_authenticated":False,
            "warning":"Prospective research only; no sportsbook EV or certified betting decisions."}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--history",required=True)
    ap.add_argument("--upcoming",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    history=[json.loads(x) for x in Path(args.history).read_text().splitlines() if x.strip()]
    fixtures=json.loads(Path(args.upcoming).read_text())
    result=run(history,fixtures)
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"forecasts":len(result["forecasts"]),"status":"HOLD","created_utc":result["created_utc"]}))

if __name__=="__main__":
    main()
